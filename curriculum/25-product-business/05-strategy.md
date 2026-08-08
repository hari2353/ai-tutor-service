# Strategy: Porter's Five Forces, Moats and Which Ones Actually Hold in Software, Build-vs-Buy, Platform vs Product, Wardley Maps

> **Track:** T25 Product Thinking & Business (MBA) · **Time:** 2h · **Prereqs:** T25-metrics · **Updated:** 2026-08-08
> **Module id:** `T25-strategy` · **Tags:** strategy

## The 30-second version

Strategy frameworks exist to answer one question an engineer is otherwise tempted to skip: not "can we build this" but "will building this still matter in three years, and can someone else erase our advantage cheaply." Porter's Five Forces tells you how much of an industry's value a company can actually keep (rivalry, buyer power, supplier power, threat of substitutes, threat of new entrants) — most software categories score badly on multiple forces at once, which is why differentiation and lock-in get chased so aggressively. Hamilton Helmer's 7 Powers is the sharper tool for "does *this specific* advantage survive contact with a competitor," and in AI specifically, most of what looks like a moat (a clever prompt, a thin wrapper around a foundation model) isn't one, because the foundation-model layer itself commoditizes the thing you'd need to be scarce; what actually holds is proprietary data with real refresh dynamics, deep workflow embedding (switching costs), and process power earned through unglamorous edge-case engineering that a fast-follower can't shortcut. Build-vs-buy and platform-vs-product decisions are the same question in a different guise — Wardley mapping makes it structural rather than emotional by placing each component of your value chain on an evolution axis (genesis → custom-built → product → commodity) and reading off the answer: build at genesis where nobody else has solved it yet, buy or rent once it's commoditized, and the single most expensive strategic mistake is building custom infrastructure for something that's already sliding toward commodity while you're investing in it.

## Why this gets asked

The interviewer has watched an engineering org spend two years building something in-house that a vendor now sells for $30k/year, or has watched a company burn its differentiation by building on a layer (a specific LLM's quirks, a specific cloud's proprietary API) that commoditized out from under them. At staff/principal level, they want evidence you think about *where value accrues over time*, not just whether a system works today — because the technical decisions you make (what to build vs. buy, what to own vs. rent, where to invest scarce engineering time) are strategy decisions whether or not anyone labels them that way, and a principal engineer who can't reason about this is dangerous with a large budget.

---

## Lineage: past → present → future

**What came before.** Corporate strategy before the 1980s was dominated by portfolio-planning tools like the BCG growth-share matrix (1970s) — cash cows, stars, dogs, question marks — which reasoned about a company's *portfolio* of businesses but said little about *why* any individual business was profitable or defensible. Michael Porter's *Competitive Strategy* (1980) filled that gap with the Five Forces framework, borrowing from industrial organization economics: an industry's average profitability is structurally determined by the intensity of five forces, and a company's job is to find or create a position where those forces bite less hard on it than on its competitors. This was hugely influential and is still taught in nearly every MBA program, but it has a well-documented blind spot even its supporters acknowledge: it was built for industrial-era, roughly-static industry structures, and says relatively little about *how* a specific company builds a defensible position that survives inside a given industry structure, or about platform/network dynamics that barely existed as a category in 1980.

**Where it stands now.** Hamilton Helmer's 7 Powers (2016, *7 Powers: The Foundations of Business Strategy*) is the modern complement most practitioners reach for alongside or instead of Porter when the question is company-specific defensibility rather than industry-level attractiveness: scale economies, network economies, counter-positioning, switching costs, branding, cornered resources, and process power — each a distinct mechanism by which a company keeps competitors from eroding its margin, evaluated on two axes (does it give a real benefit, does it persist over time). Wardley mapping (Simon Wardley, developed through the 2000s-2010s, popularized via his "On Being Lost" and later book-length writing) is the newer arrival in mainstream practitioner use, specifically aimed at situational awareness for build-vs-buy and technology investment decisions — it doesn't replace Porter or Helmer, it operates one layer down, at the level of "which specific components of my value chain should I build, buy, or rent, given where each one sits on an evolution curve." The live disagreement isn't really about which framework is "right" — practitioners increasingly use them as complementary lenses (Porter/Helmer for "is this position defensible," Wardley for "which components should I own") — it's about **how applicable classic moat thinking is to AI specifically**, where the input factor (foundation model capability) is itself evolving so fast that a moat built on model capability alone can evaporate within a product cycle; the emerging consensus, discussed below, is that this shifts which of the classic powers still apply, not that the powers stop mattering.

**Where it's heading.** High confidence: Wardley-style evolution thinking keeps spreading in engineering organizations specifically (versus staying confined to strategy/consulting circles) because it maps directly onto build-vs-buy decisions engineers already have to make, and AI-infrastructure decisions (which parts of an agent stack to build vs. adopt from a fast-moving ecosystem) are forcing this question weekly rather than annually. Moderate confidence: practitioner framing of AI moats is consolidating around "cornered resources shift from raw data to *rights-cleared, continuously refreshed* data" and "process power shifts from having a model to having the unglamorous edge-case and evaluation engineering that gets a system to reliable production behavior" — both actively discussed in 2025-2026 strategy writing, not yet fully settled doctrine. More speculative: as agentic AI systems increasingly compose multiple vendors' capabilities dynamically, some strategists are arguing the "build vs buy" binary itself is dissolving into a continuous "orchestrate vs. own" spectrum — interesting, unresolved, worth naming as a live debate rather than citing as settled.

---

## Mental model

```
PORTER'S FIVE FORCES                    WARDLEY EVOLUTION AXIS
     (how much value can this            (where does each COMPONENT of
      industry position keep?)            your value chain sit, and where
                                           is it heading?)
   THREAT OF                            GENESIS ── CUSTOM-BUILT ── PRODUCT ── COMMODITY
   NEW ENTRANTS                          (novel,     (maturing,     (widely    (utility,
        │                                 build it     still         available   rent/buy
        ▼                                 yourself,    scarce,       from        it, e.g.
  SUPPLIER ◀── RIVALRY ──▶ BUYER           nobody       build or      several     cloud
  POWER          (center)   POWER          else has     buy either    vendors)    compute)
        ▲                                  solved it    way)
        │
   THREAT OF
   SUBSTITUTES

  Porter tells you if the INDUSTRY is worth being in.
  Wardley tells you, component by component, whether to BUILD, BUY, or RENT --
  and warns you when you're building custom infrastructure for something
  that's already sliding toward commodity while you invest in it.
```

---

## How it actually works

### Porter's Five Forces, applied to software specifically

- **Threat of new entrants** — historically low-to-moderate for software (low capital requirements to start a company) but the real barrier is distribution and trust, not capital; in most SaaS categories this force is high because a competitor can spin up a credible MVP fast, which is exactly why differentiation strategies (below) matter so much more in software than in capital-intensive industries.
- **Bargaining power of suppliers** — for most software companies, "suppliers" means cloud infrastructure, foundation-model APIs, and critical third-party data/services. This has gotten *more* concentrated and *more* powerful for AI-dependent companies specifically: a company built entirely on one foundation-model provider's API has a supplier with enormous pricing and roadmap power over it, which is a real strategic vulnerability worth naming explicitly rather than treating as a pure implementation detail.
- **Bargaining power of buyers** — high when switching cost is low and there are many substitutable vendors (commodity SaaS categories), low when the product is deeply embedded in a workflow or has high switching cost (see switching-costs power below) — buyer power is often the force a company has the most direct control over, via how it designs the product's stickiness.
- **Threat of substitutes** — the JTBD-style question from the discovery module applied at industry level: what's hired instead of your product category entirely (a spreadsheet instead of a project-management tool, an internal script instead of a paid API), not just what's hired from a direct competitor.
- **Competitive rivalry** — the center force, intensified by low differentiation, high fixed costs relative to marginal costs (software's classic near-zero marginal cost structure pushes toward aggressive price competition once a category commoditizes), and low switching costs.

The honest read on most software categories: several forces are simultaneously unfavorable — low barriers to entry, low buyer switching costs in undifferentiated tooling, and for AI-dependent companies specifically, high and rising supplier power from foundation-model providers. This is precisely why the industry's strategic conversation has shifted so heavily toward moats (Helmer's framing) — Porter tells you the default outcome is thin margins, so a company has to construct a specific, defensible position that resists these forces rather than assuming the category itself is attractive.

### Which of Helmer's 7 Powers actually hold in software, and which are weaker than founders think

Helmer's seven — scale economies, network economies, counter-positioning, switching costs, branding, cornered resources, process power — evaluated for software/AI specifically, with an honest read on which ones a typical engineering-led startup can realistically build:

- **Scale economies** — real in categories with strong fixed-cost amortization (a marketplace's matching algorithm gets better with more data at scale, spreading engineering cost over more users) but weaker than it looks for most SaaS, where marginal cost of serving one more customer is already near zero and the "scale" benefit is more about brand/distribution than a genuine cost curve advantage.
- **Network economies** — genuinely one of the strongest moats when real (each additional user makes the product more valuable to every other user — marketplaces, communication tools, some data-network-effect products), but frequently claimed and rarely actually present; "more users means more data means a better product" is a network effect only if that better product is *itself* hard for a competitor to replicate with less data, which for many ML features (isn't, once a foundation model handles most of the heavy lifting) is not true.
- **Counter-positioning** — a new entrant adopts a business model the incumbent can't copy without damaging its existing business (the classic example being a low-cost or different-model entrant the incumbent would cannibalize itself to match) — real, but hard to engineer deliberately; usually recognized in hindsight more than planned in advance.
- **Switching costs** — one of the most reliably real moats in enterprise software specifically: deep workflow embedding, data lock-in, integration surface area, and retraining cost all compound the longer a customer is on a platform. This is the power most within an engineering org's direct control to build (deeper integrations, more embedded workflows, more accumulated customer-specific configuration/data) and arguably the one worth the most deliberate investment.
- **Branding** — real but slow to build and usually not the lever an engineering-led company should lead with; more relevant to consumer categories than the B2B/infra categories this curriculum's target audience mostly works in.
- **Cornered resources** — has shifted meaning specifically in the AI era: raw proprietary datasets are less defensible than they used to be (foundation models are trained on enormous public and licensed corpora, eroding the advantage of "we have data"), but *rights-cleared, continuously refreshed, proprietary* data — data a competitor genuinely cannot get, updated faster than a competitor could re-derive it — remains a strong cornered resource. Scarce specialized talent and proprietary hardware/infrastructure access are the other live examples.
- **Process power** — the moat most underestimated by teams that think "anyone can build a ChatGPT wrapper in a weekend," which is true and exactly the point: the wrapper is trivial, but getting a system to 99%+ reliable accuracy on a mission-critical task in production requires years of unglamorous edge-case handling, evaluation infrastructure, and operational tuning that a fast-follower building the same wrapper cannot shortcut by copying the visible product — this is one of the more durable moats available to an AI-product team specifically, and it's earned, not designed in on day one.

**The honest synthesis for an AI product specifically:** a thin prompt or wrapper around a foundation model is not a moat — the foundation-model layer itself is evolving too fast and commoditizing too quickly for that layer alone to be defensible. What holds is the combination of process power (production-grade reliability engineering) with switching costs (deep workflow embedding) and, where genuinely available, cornered resources (proprietary, continuously refreshed, rights-cleared data) — durable advantage in AI products comes from *how the powers interact*, not any single one alone.

### Build vs. buy, and platform vs. product, through the Wardley lens

Wardley's core move is putting every component of a value chain on an **evolution axis**: **genesis** (novel, nobody's solved this, you're inventing) → **custom-built** (maturing, still scarce, meaningfully differentiated by who builds it well) → **product** (mature, multiple vendors, clear feature comparisons) → **commodity/utility** (standardized, interchangeable, usually cheapest to just rent). The build-vs-buy answer follows directly from where a component sits: **build at genesis** (nobody sells what you need yet, and building it might itself be your differentiation), **build or carefully evaluate custom options in custom-built** (real differentiation still available, but increasingly risky to over-invest in as the space matures), **buy in product** (multiple vendors, comparison-shop, building custom here is usually pure opportunity cost), **rent/consume as utility in commodity** (compute is the canonical example — it took roughly four decades to move from genesis, a genuine differentiator for a company able to build its own, to commodity, something every company just rents from a cloud provider; a modern engineering org that still insists on running its own data centers for undifferentiated compute is paying a real strategic tax for no corresponding advantage).

The mechanically useful part of this for a build-vs-buy decision under real pressure: **components keep moving right (toward commodity) over time, driven by competition and standardization, and the direction of movement matters more than the current snapshot.** A component that's "product" stage today but visibly moving toward commodity (multiple vendors racing to undercut each other, standardization emerging) is a bad candidate for a multi-year custom build even if buying looks marginally more expensive right now, because you'd be locking in custom-maintenance cost for something the market is about to make nearly free. This is exactly the mistake documented in banking's core-systems history: billions invested in custom-built core-banking systems between roughly 2010-2020, at the same time those systems were visibly transitioning toward the product stage — a Wardley map, drawn honestly, would have shown the investment was fighting the evolution direction, not riding it.

**Platform vs. product** is the same evolution-axis question applied to your own offering: a product solves one job well for one customer at a time; a platform provides the underlying capabilities that let many parties (including third parties) build many different solutions on top. The strategic question is whether the *capability* you're building is itself heading toward commodity (in which case platform-izing it and monetizing usage/ecosystem value is often the better long-term position than trying to hold a product-layer moat on a capability everyone will soon have) or whether it's still differentiated enough that a tightly-integrated product experience captures more value than an open platform would. Getting this backwards — platform-izing too early, before the underlying capability is differentiated enough to anchor an ecosystem, or product-izing too late, defending a feature that's already commoditizing, are both common, expensive strategic errors.

---

## Build it from scratch

No code lab; the artifact worth building is a one-page Wardley-style map of your own team's actual stack, which is a genuinely useful exercise to walk into a build-vs-buy debate with.

```text
# untested sketch — a minimal text-based Wardley map for an AI product's stack

VISIBILITY (top = user-facing, bottom = invisible infrastructure)
  high  │  chat UI / product experience          [custom-built, differentiating]
        │  agent orchestration logic              [custom-built -> moving toward product
        │                                          as frameworks like LangGraph mature]
        │  retrieval / RAG pipeline               [custom-built, still real differentiation
        │                                          in eval quality and domain tuning]
        │  vector database                        [product -> commodity: many vendors,
        │                                          increasingly interchangeable via
        │                                          standard interfaces]
        │  foundation model (LLM API)              [product, moving fast, NOT a moat --
        │                                          swap-able, commoditizing within a
        │                                          product cycle]
  low   │  GPU compute                             [commodity/utility -- rent from cloud,
        │                                          building your own is a strategic tax
        │                                          with no corresponding advantage]
        └──────────────────────────────────────────────────────────────────────────
          GENESIS        CUSTOM-BUILT        PRODUCT           COMMODITY
                    EVOLUTION AXIS (driven by competition, moves left -> right)

# Read: build/differentiate where you're custom-built or genesis and the
# component is user-visible and hard to replicate (retrieval quality, agent
# reliability engineering). Buy/rent everything sliding toward commodity
# (vector DB, GPU compute, the model itself) -- don't spend engineering
# time defending a position the market is about to make free.
```

---

## How it's done in production

| Symptom | Cause | Fix |
|---|---|---|
| Team spent a year building a custom vector database layer, a managed vendor now does it cheaper and better | Misjudged where the component sat on the evolution axis — built custom for something already moving toward product/commodity | Re-map the stack periodically (quarterly/at major planning cycles), not just once at project kickoff — evolution keeps moving |
| Product's only defensible advantage is "we use GPT-5" or similarly names a specific foundation model | No real moat — the foundation-model layer is a commodity/product-stage input, not a cornered resource; a competitor can switch providers as easily as you did | Identify and invest in what's actually defensible: process power (production reliability), switching costs (workflow embedding), or genuinely proprietary refreshed data |
| Company platform-ized a capability before any third party wanted to build on it | Platform-ized before the underlying capability was differentiated enough to anchor an ecosystem — no demand for the "platform" half of the value proposition yet | Validate real third-party demand (a discovery-style check) before investing in platform surface area; ship as a product first, platform-ize once demand for extensibility is evidenced |
| Company defends a product-layer feature that's visibly commoditizing across the whole category | Product-izing too late — competitors and open-source alternatives are already racing the feature toward free | Redirect investment toward the layer above (better integration, workflow embedding) or below (infrastructure efficiency) that isn't commoditizing as fast |
| Team names "our data" as a moat with no specifics | Cornered-resources claim without checking whether the data is actually rights-cleared, genuinely proprietary, and refreshed faster than a competitor could re-derive it | Audit the specific claim: is this data legally exclusive, and does its value decay fast enough that "having more of it, faster" is a real, ongoing advantage, not a one-time head start |

---

## Tradeoffs & when NOT to use it

- **Don't run a full Wardley mapping exercise for a tactical, low-stakes build-vs-buy call** (which logging library to use). Reserve it for decisions with multi-year, hard-to-reverse infrastructure or strategic implications.
- **Porter's Five Forces is an industry-level lens; it says little about company-specific execution.** Two companies in the identical industry position can have wildly different outcomes based on execution quality that Porter's framework doesn't capture — pair it with Helmer's powers (company-specific) rather than treating industry attractiveness alone as destiny.
- **Don't claim a moat you haven't actually tested against a determined competitor.** Many "network effects" and "switching costs" claimed in pitch decks evaporate the moment a well-resourced competitor tries seriously to break them — the honest test is "would this survive a well-funded competitor spending two years specifically trying to replicate it," not "does it sound defensible in a meeting."
- **Building custom at the genesis stage is right only if the capability is genuinely core to your differentiation** — building custom infrastructure for a genesis-stage component that isn't actually your differentiator (e.g., building a custom training pipeline when your differentiation is really in domain-specific evaluation and data curation) burns scarce engineering time on the wrong layer.
- **Platform strategies carry real organizational cost** (API stability commitments, backward compatibility, third-party support burden) that a pure product strategy doesn't — don't platform-ize reflexively because it sounds more ambitious; it's the right call only when ecosystem value genuinely exceeds the cost of supporting one.

---

## Interview questions

### Q1 — Walk through Porter's Five Forces for a company building an AI-powered SaaS product on top of a foundation-model API.
**Answer:** New entrants: low barrier (anyone can call the same API), high threat. Supplier power: high and rising — the foundation-model provider has significant pricing and roadmap control over you. Buyer power: depends entirely on switching cost you've built into the product, not on the underlying AI. Substitutes: not just competing AI products, but the JTBD-style "what's hired instead" — a human doing the task manually, an internal script, a general-purpose chat assistant used ad hoc. Rivalry: intensified by near-zero marginal cost and low differentiation if the product is a thin wrapper. The honest read: several forces are unfavorable by default, which is exactly why the company needs a specific, engineered moat rather than assuming the category is attractive.
**Follow-up trap:** *"Which single force would you focus on improving first?"* — buyer power via switching costs (deep workflow embedding), because it's the one most directly within engineering's control, versus supplier power (largely outside your control short of multi-provider abstraction) or rivalry (structural to the category).

### Q2 — Is "we have more data than our competitors" a real moat? When is it and when isn't it?
**Answer:** It's real specifically when the data is rights-cleared (you can legally use it and competitors legally can't get equivalent data), genuinely proprietary (not derivable from public/licensed corpora foundation models are already trained on), and refreshed faster than a competitor could re-derive an equivalent dataset. It's not real when it's a one-time head start that a competitor with a comparable product could catch up on within a normal product cycle, or when a foundation model's general capability already covers most of the value the data would have added.
**Follow-up trap:** *"How would you actually test this claim before betting a strategy on it?"* — estimate how long it would take a well-resourced competitor to acquire or approximate equivalent data (partnership, licensing, synthetic generation, a different data source that serves the same downstream purpose) — if the answer is "a few months with a licensing deal," it's not a durable cornered resource.

### Q3 — Explain Wardley mapping's evolution axis and how it changes a build-vs-buy decision.
**Answer:** Every component of a value chain sits somewhere on genesis → custom-built → product → commodity, and moves rightward over time driven by competition and standardization. Build (or seriously evaluate custom) at genesis/custom-built where real differentiation still exists; buy at product stage where multiple vendors compete; rent/consume as utility at commodity, where building custom is a strategic tax with no corresponding advantage. The key addition beyond a snapshot decision: the *direction* a component is moving matters as much as its current stage — a component moving fast toward commodity is a bad multi-year custom-build bet even if buying looks marginally pricier today.
**Follow-up trap:** *"Give a real example of a company that got this wrong."* — the banking industry's core-systems investment: billions spent on custom-built core-banking systems roughly 2010-2020 while those systems were visibly transitioning toward the product stage — the investment fought the evolution direction instead of riding it.

### Q4 — Your team wants to platform-ize your product's agent-orchestration layer so third parties can build on it. How do you evaluate this?
**Answer:** Check whether there's actual evidenced third-party demand to build on top of it (a discovery-style validation, not a hunch) before investing in platform surface area (API stability, backward compatibility, third-party support burden are real, ongoing costs). Also check where the underlying capability sits on the evolution axis — platform-izing a capability that's itself racing toward commodity (many open-source agent orchestration frameworks maturing quickly) may mean you're building ecosystem infrastructure around something that won't be differentiated enough to anchor real demand.
**Follow-up trap:** *"What if a competitor platform-izes first and captures the ecosystem?"* — being first to platform-ize a genesis/custom-built-stage capability with real demand is a legitimate first-mover play; the mistake this question is testing for is platform-izing reflexively, out of ambition, without validating demand or checking the evolution trajectory — being fast and being validated aren't mutually exclusive, but skipping validation to be fast is the common failure.

### Q5 — Why is "we use GPT-5 / Claude / [specific foundation model]" not a moat, even if your product is genuinely good?
**Answer:** The foundation-model layer is at product stage, moving toward commodity, with multiple credible competing providers and increasingly standardized interfaces — a competitor can switch to (or already use) the same or an equivalent model with comparable ease. Whatever is genuinely good about your product has to live in a layer that's harder to replicate: production reliability engineering (process power), deep workflow/data integration (switching costs), or genuinely proprietary data — not in which model API you call.
**Follow-up trap:** *"What if you have exclusive access to a specific model or fine-tune?"* — that can be a real, if often temporary, cornered resource — evaluate it the same way as any cornered-resource claim: is it legally exclusive, and does the exclusivity outlast the pace at which the rest of the field catches up or the provider extends access more broadly (many "exclusive" early-access arrangements are time-limited by design).

### Q6 — Explain process power as a moat and why it's specifically underestimated by teams building AI wrappers.
**Answer:** Process power is advantage earned through years of accumulated, hard-to-copy operational excellence — not a single clever technique, but the compounding effect of countless edge-case fixes, evaluation infrastructure, and production tuning. It's underestimated for AI wrappers specifically because the visible product (the wrapper, the prompt, the UI) is genuinely easy to copy over a weekend, which makes teams (and competitors) assume the whole thing is easy to copy — but the invisible 99%+ production reliability on a mission-critical task is not visible in the product's surface and takes years to replicate honestly, not weeks.
**Follow-up trap:** *"How do you know your team actually has process power, versus just believing it does?"* — check whether a well-resourced competitor with access to the same foundation models could replicate your production reliability within a normal product cycle by copying only what's externally visible — if yes, you don't have process power yet, you have a head start; process power is the thing that survives a competitor trying and still taking years.

### Q7 — When would you deliberately build custom infrastructure for a component that's already at "product" stage, buyable from multiple vendors?
**Answer:** When the component, despite being commercially available, is close enough to your core differentiation that vendor limitations materially constrain your product (a vendor's rate limits, data residency restrictions, or feature gaps block something central to your value proposition), or when the total cost of ownership genuinely favors build at your specific scale and usage pattern — but this should be a deliberate, cost-justified exception, not the default, and it should be revisited as the market matures further.
**Follow-up trap:** *"How do you avoid this turning into 'not invented here' syndrome dressed up as strategy?"* — require an explicit, written cost/differentiation justification before a custom build at product stage is approved, reviewed by someone outside the team proposing it — the discipline of writing it down and getting outside review is what separates a real strategic exception from engineers preferring to build their own version of something that already exists.

### Q8 — Compare Porter's Five Forces and Helmer's 7 Powers. When would you use one over the other in a real strategy conversation?
**Answer:** Porter operates at the industry level — how attractive is this space to compete in, given structural forces largely outside any one company's control. Helmer operates at the company level — given you're in this space, what specific, durable mechanism protects your margin from competitors. Use Porter early, when deciding whether to enter a market or category at all; use Helmer once you're in it, to decide what to actually invest scarce engineering and product effort in building.
**Follow-up trap:** *"Porter says the industry is unattractive but Helmer suggests you can build a strong power anyway — which do you trust?"* — Helmer, if the power is real and well-evidenced — Porter describes the *average* outcome for participants in a structurally difficult industry, not a ceiling on any individual company's outcome; a company with a genuine, tested power (e.g. real switching costs plus real process power) can outperform an unattractive industry's average significantly, which is exactly the strategic bet worth making explicit rather than assumed.

### Q9 — A stakeholder claims "our network effects" as a moat for a B2B SaaS tool with 200 customers. How do you stress-test this?
**Answer:** Ask specifically what makes the product better for existing users as new users join — a real network effect requires that mechanism to exist, not just "more users, more data, presumably better." Check whether the improvement from additional users is large enough and specific enough that a competitor starting from zero would face a genuine structural disadvantage, versus a modest, catchable data advantage. At 200 customers in B2B specifically, most "network effects" claims are actually switching-cost claims (integration depth, accumulated configuration) mislabeled — a legitimate but different power with a different investment thesis.
**Follow-up trap:** *"What's the practical difference in what you'd invest in, depending on which power it actually is?"* — a real network effect justifies investing in things that increase cross-user value (matching quality, shared benchmarks, network-visible features); a switching-cost power justifies investing in deeper integration and higher migration cost instead — misdiagnosing which power you actually have leads to investing in the wrong lever.

### Q10 — Design the strategic argument (not the technical one) for why your AI feature should exist, using this module's frameworks.
**Testing:** synthesis — can you build a coherent multi-framework argument, not just recite definitions.
**Answer:** Start with Porter: name the specific forces this feature affects — does it raise buyer switching cost, does it reduce dependence on a powerful supplier (e.g., by abstracting the foundation-model layer), does it raise barriers for new entrants targeting your customer base. Then name the specific Helmer power(s) it's meant to build — most credibly process power (if it requires genuine reliability engineering competitors would need years to match) and/or switching costs (deeper workflow embedding) — and be honest about which powers it does *not* build (rarely network effects or branding for most B2B AI features). Then place its core technical components on a Wardley evolution axis to justify what should be built custom versus bought, so the build effort itself is spent on the layer that's actually differentiating, not on infrastructure that's commoditizing underneath you.
**Follow-up trap:** *"What would make you conclude this feature is NOT worth building, using the same frameworks?"* — if it doesn't measurably shift any of the five forces in your favor, doesn't build a specific Helmer power beyond "we shipped it before a competitor," and its core technical value sits at a Wardley stage that's rapidly commoditizing (meaning any advantage is temporary by construction) — a credible answer here, not just a credible case for building, is what separates strategic reasoning from a sales pitch for your own feature.

---

## Red flags that fail you

- Naming "we use [a specific foundation model]" as a competitive moat without qualification.
- Claiming a network effect without being able to describe the specific mechanism by which more users make the product better for existing users.
- Recommending Porter's Five Forces as the tool for a company-specific build-vs-buy decision (it's an industry-level lens, not a component-level one).
- No mention of the evolution axis or direction-of-travel when discussing a multi-year build-vs-buy decision — treating it as a static snapshot.
- Treating "our data" as self-evidently a moat without checking whether it's rights-cleared, genuinely proprietary, and refreshed faster than a competitor could catch up.
- Recommending platform-izing a capability with no evidence of third-party demand.

---

## Cheat card

```
PORTER 5 FORCES   rivalry (center) / buyer power / supplier power / threat of
                  substitutes / threat of new entrants -- INDUSTRY-level: how
                  much value can ANY participant in this category keep
                  software: usually low entry barriers + low switching cost in
                  undifferentiated tooling + rising supplier power from
                  foundation-model providers = unfavorable by default

HELMER 7 POWERS   COMPANY-level: does THIS advantage survive a competitor
                  scale economies      -- weak for most SaaS (near-zero marginal cost)
                  network economies    -- strong IF real; most claims are overstated
                  counter-positioning  -- real, rarely engineered deliberately
                  switching costs      -- most reliably buildable in B2B/enterprise
                  branding             -- real, slow, usually not eng-led lever
                  cornered resources   -- AI-era: rights-cleared + continuously
                                          refreshed data beats raw data volume
                  process power        -- underestimated: 99%+ prod reliability via
                                          years of edge-case eng, NOT the visible wrapper

AI-SPECIFIC       thin prompt/wrapper on a foundation model = NOT a moat (model
                  layer commoditizing fast). Durable: process power + switching
                  costs + (if real) cornered resources, IN COMBINATION

WARDLEY EVOLUTION genesis -> custom-built -> product -> commodity/utility
                  build at genesis; build/evaluate at custom-built; BUY at product;
                  RENT at commodity (compute: ~40yr genesis->commodity)
                  DIRECTION matters more than snapshot -- don't custom-build a
                  multi-year bet on something already sliding toward commodity
                  (banking core-systems 2010-2020: built custom while the
                  category moved toward product -- fought the evolution direction)

PLATFORM v PRODUCT  platform-ize only with EVIDENCED 3rd-party demand + the
                    underlying capability differentiated enough to anchor an
                    ecosystem; premature platform = real ongoing API/support cost
                    for no corresponding demand
```

## Sources

- [Porter's 5 Forces Model: Complete 2026 Guide + Examples — FourWeekMBA](https://fourweekmba.com/porter-five-forces/) — accessed 2026-08-08
- [Moats in the Age of AI — Tanay Jaipuria](https://www.tanayj.com/p/moats-in-the-age-of-ai) — accessed 2026-08-08
- [The 7 Most Powerful Moats For AI Startup — Y Combinator Library](https://www.ycombinator.com/library/Mx-the-7-most-powerful-moats-for-ai-startup) — accessed 2026-08-08
- [Evolution Stages — Wardley Maps Glossary](https://www.wardleymaps.com/glossary/evolution-stages) — accessed 2026-08-08
- [Build vs Buy in 2026: Using Wardley Mapping to Navigate the Agentic AI Shift — Medium](https://medium.com/@haberlah/build-vs-buy-in-2026-using-wardley-mapping-to-navigate-the-agentic-ai-shift-be24d534b054) — accessed 2026-08-08
- Michael Porter, *Competitive Strategy* (1980)
- Hamilton Helmer, *7 Powers: The Foundations of Business Strategy* (2016)

## Changelog
- 2026-08-08 — created
