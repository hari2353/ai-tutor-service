# POC → Prototype → MVP → Production: What Changes at Each Gate

> **Track:** T10 System Design · **Time:** 2.5h · **Prereqs:** `T10-design-method`, `T10-tech-selection` · **Updated:** 2026-08-02
> **Module id:** `T10-poc-to-prod` · **Tags:** delivery, critical

## The 30-second version

Four stages, each answering one specific question and nothing more: a POC (days, throwaway code) answers "is this technically possible at all," a prototype (1-3 weeks, still throwaway) answers "does this solve the right problem for a real user," an MVP (weeks to a couple months, first non-throwaway code) answers "will anyone actually use and pay for this at small scale," and production answers "will this hold up under real load, real failure modes, real operators, and real cost accounting, indefinitely." The single most expensive mistake in this pipeline is skipping a gate's *question* while reusing its *code* — carrying POC code into production because it "already works" is why 88% of enterprise AI pilots never reach production and RAND's 2025 analysis found 80.3% of AI projects fail to deliver intended business value, mostly for organizational reasons (data readiness, unclear ownership, no eval infrastructure) rather than model capability. Each gate should change the code's assumptions about scale, failure, and cost, not just add features to what came before.

## Why this gets asked

Because the interviewer has personally watched a demo-quality POC get fast-tracked into production because it "worked in the demo," and then watched it fall over on real traffic, real messy data, or a failure mode nobody tested because nobody was supposed to test — it was a POC. They want to know if you can name, concretely, what has to actually change at each gate (not just "harden it more"), whether you know the current statistics on why AI projects specifically die between pilot and production, and whether you'll push back on pressure to skip a gate under a deadline rather than silently inheriting technical debt that becomes someone else's 2am page.

---

## Lineage: past → present → future

**What came before.** The waterfall era had one gate: a requirements document, followed by monolithic development straight to launch, with no intermediate validation of feasibility or usability before heavy investment — the well-documented failure mode was discovering in the final months that the fundamental approach didn't work, after most of the budget was spent. Lean Startup (Eric Ries, 2011) introduced the MVP as a reaction to this specific pain — build the smallest thing that tests a real hypothesis with real users, rather than fully building a vision before learning whether it's wanted. Hardware engineering had already formalized a more granular staged-gate model decades earlier (EVT/DVT/PVT — engineering, design, and production validation test, standard in consumer electronics manufacturing since well before software adopted similar thinking), precisely because a hardware mistake caught after tooling is committed costs orders of magnitude more to fix than one caught on a 3D-printed prototype — the same economic argument software teams eventually absorbed for their own staged gates.

**Where it stands now.** The consensus shape (POC → Prototype → MVP → Production) is now standard vocabulary, but the live disagreement is about how rigorously the four stages are actually distinct in practice versus treated as a single continuum with different names slapped on the same code as it ages. What's changed sharply and recently: with generative AI features, the gap between "pilot" and "production" has become the dominant failure point industry-wide, at a scale not seen in prior technology waves — a March 2026 survey of 650 enterprise technology leaders found 78% of enterprises have AI agent pilots running, but only 14% have scaled one to organization-wide operational use. MIT-associated research reported roughly 95% of enterprise AI pilots deliver zero measurable P&L impact. RAND's 2025 analysis is the most granular public breakdown: 80.3% of AI projects fail to deliver intended business value, split as 33.8% abandoned before reaching production at all, 28.4% completing but underdelivering, and 18.1% delivering some value but failing to justify their cost. The consistent finding across all of these: the primary causes are organizational and operational (data readiness, unclear ownership, missing evaluation infrastructure, change management) rather than model or algorithm quality — which directly validates that the POC→prod gate structure, done properly, is not bureaucratic overhead but the actual mechanism that catches these failure modes before they're expensive.

**Where it's heading.** The direction of travel for AI-specific pilots is toward formalizing an **evaluation-infrastructure gate** as a first-class stage of its own, sitting between MVP and production specifically for ML/LLM-backed features — the argument, increasingly explicit in 2026 industry writing, is that traditional software's MVP→production gate (mostly about scale, reliability, and ops) is necessary but insufficient for AI features, which additionally need a golden-set evaluation harness, drift monitoring, and a defined "good enough" quality bar established *before* production traffic, not discovered from user complaints after. Treat this as an emerging, not yet universally standardized, addition to the classic four-gate model — most organizations are still converging on where exactly it belongs and how heavy it should be.

---

## Mental model

Each gate exists to retire a specific category of risk before the next, more expensive stage commits real cost to it. Skipping a gate doesn't remove the risk — it just means the next, more expensive stage discovers it the hard way.

```
  POC              PROTOTYPE           MVP                  PRODUCTION
  ────             ─────────           ───                  ──────────
  "Can this        "Is this the        "Will real users      "Will this hold up
   be built         right thing         actually use          under real load,
   at all?"         to build?"          and pay for           real failure, real
                                         this, minimally?"     cost, indefinitely?"

  risk retired:     risk retired:       risk retired:         risk retired:
  TECHNICAL         PRODUCT/UX          MARKET/ADOPTION       OPERATIONAL/SCALE

  code: throwaway   code: throwaway     code: first real,     code: hardened,
                    (or thin wrapper                          observable, on-call'd,
                    over POC)           small-scale prod                       cost-accounted

  audience: you,    audience: a         audience: real        audience: all real
  maybe your        handful of real     paying/committed      traffic, including
  team              target users        early users            adversarial and
                                                                edge-case users

  if skipped →      if skipped →        if skipped →          (this is the one you
  MVP discovers     MVP/prod discovers  production discovers  can't skip — it's
  "it can't be      "nobody wants       "it falls over at     what everything else
  built" at 10x      this" at 10x        10x the cost"        was preparing for)
  the cost           the cost
```

The number that should scare you into never skipping a gate: RAND's finding that a third of AI projects (33.8%) are abandoned *before* production — meaning the technical-feasibility and product-fit risks these early gates exist to catch are still, at massive scale, being discovered only after most of the investment is already spent, which is precisely the waterfall-era failure mode this whole staged model was invented to prevent.

---

## How it actually works

### POC (Proof of Concept) — days to ~2 weeks

**Question:** is this technically possible, roughly, at all — ignoring UX, ignoring scale, ignoring cost.

**What you build:** the smallest, ugliest thing that answers the specific technical unknown. If the unknown is "can we get acceptable latency doing RAG retrieval against our document corpus," the POC is a script that embeds a sample of documents, runs retrieval, and measures latency and relevance on ten hand-picked queries — no UI, no auth, no error handling, hardcoded paths, run from a notebook.

**What you deliberately do NOT build:** anything related to how a real user interacts with it, anything related to scale beyond a small sample, any production-quality error handling, any authentication or multi-tenancy.

**Exit criteria:** a specific technical question has a yes/no answer with evidence, not a vibe. "Retrieval latency was 340ms p50 on a 50k-document sample, relevance judged acceptable on 8/10 hand-picked queries" is an exit criterion. "It seemed to work" is not.

**The trap:** POC code has a gravitational pull toward becoming production code because it already "does the thing," and under deadline pressure, someone decides to just harden it in place rather than rewrite. This is how a notebook script with a hardcoded API key ends up, eighteen months later, still running in production with the same hardcoded key rotated only when it accidentally leaks.

### Prototype — 1-3 weeks

**Question:** is this the right thing to build — does it actually solve the user's problem in a way they'd recognize as valuable, before you invest in making it real.

**What you build:** something a real target user can react to, focused entirely on UX and value proposition, not robustness. Often explicitly fake underneath — a "Wizard of Oz" prototype where a human manually does what the AI would eventually do, or hardcoded/mocked responses behind a real-looking UI, specifically because building the real backend before validating the interaction is wasted effort if the interaction is wrong.

**What changes from POC:** audience (real target users, not just your team), what's being tested (usability and value, not raw technical feasibility), and disposability discipline (still throwaway, but now throwaway *after* it's shown to people, which requires slightly more polish than a POC ever needs).

**Exit criteria:** specific, observed user reactions to a specific interaction, not opinions gathered in the abstract — "6 of 8 target users completed the core task without guidance and said they'd use this over their current workflow" is an exit criterion; "the demo went well" is not.

### MVP (Minimum Viable Product) — weeks to a couple months

**Question:** will real users adopt this and get real value from it at small scale, with real (if minimal) infrastructure behind it.

**What you build:** the first genuinely non-throwaway code in the pipeline — a real backend, real (if minimal) data persistence, real auth, deliberately limited feature scope, running for a small cohort of real users or customers, often with a feature flag or manual gating rather than public availability.

**What changes from prototype:** it's a live, functioning product, not a facade — the "Wizard of Oz" human is gone, real requests hit real code. Observability starts here, minimally (you need to know if it's working, even at this scale). Cost starts being tracked, even roughly, because "does the unit economics work at all" is part of what MVP is supposed to answer.

**Exit criteria:** real usage and retention metrics from a real (if small) cohort, over a real (if short) time window — "40 users in the pilot cohort, 65% weekly-active after 4 weeks, unit cost per interaction is $0.12 against a target of under $0.20" is an exit criterion. A demo to leadership is not; a demo tells you nothing about whether real users return on their own.

**The AI-specific addition here, increasingly standard practice by 2026:** an evaluation harness — a golden set of inputs with known-good outputs or a rubric, run automatically against every change — needs to exist *before* this stage exits, not be bolted on after a production incident reveals quality regressed silently. This is the piece traditional (non-AI) MVP→production thinking doesn't require and AI features specifically do, because model/prompt changes can silently degrade quality in ways a traditional deploy's test suite wouldn't catch.

### Production — ongoing

**Question:** will this hold up under real load, real adversarial and edge-case behavior, real operational burden, and real cost accounting, indefinitely, with people other than the original builders able to operate it.

**What actually changes, concretely, not just "more testing":**

| Dimension | MVP | Production |
|---|---|---|
| **Scale** | Handles the pilot cohort's actual load, tested informally | Load-tested against projected peak + headroom, with a documented capacity plan |
| **Failure handling** | Errors surface, maybe logged | Full resilience catalogue — timeouts, retry+jitter, circuit breakers, bulkheads, graceful degradation, tested failure-mode by failure-mode |
| **Observability** | Basic logs, maybe a dashboard someone checks manually | Structured logging, metrics, distributed tracing, alerting with defined on-call ownership and runbooks |
| **Security** | Auth exists, may be coarse | Least-privilege access control, secrets management, dependency scanning, the security posture the org actually requires for customer-facing systems |
| **Data** | Minimal validation, may tolerate manual fixes | Schema enforcement, migration discipline, backup/restore tested (not just configured), retention policy |
| **Cost** | Tracked roughly, absolute dollars | Modeled per-unit, budgeted, alerted on anomalies, with a clear owner accountable for it |
| **Ownership** | Usually the original builders, informally | Explicit on-call rotation, runbooks, a defined incident process, bus-factor above 1 |
| **Rollback/deploy** | Manual, ad hoc, "someone SSHs in" | Automated, tested rollback path, staged rollout (canary/blue-green), documented deploy process anyone on the team can execute |
| **AI-specific: quality gate** | Spot-checked, maybe a demo | Automated eval harness gating every model/prompt change, drift monitoring on production traffic, defined quality regression threshold that pages someone |

**Exit criteria:** there isn't one, in the sense the earlier stages have — production is the state the system lives in, not a state it graduates out of. The "exit criteria" that matter here are ongoing SLOs being met, not a one-time gate passed.

---

## Build it from scratch

A minimal gate-tracking artifact — worth being able to sketch because "how would you formalize this so it's not just vibes" is a natural follow-up:

```python
from dataclasses import dataclass, field
from enum import Enum

class Gate(Enum):
    POC = "poc"; PROTOTYPE = "prototype"; MVP = "mvp"; PRODUCTION = "production"

@dataclass
class GateExit:
    gate: Gate
    question_answered: str      # the ONE question this gate exists to answer
    evidence: str                # concrete, measured evidence — never "it seemed to work"
    risk_retired: str            # technical / product-UX / market-adoption / operational-scale
    passed: bool

@dataclass
class ProjectGates:
    exits: list[GateExit] = field(default_factory=list)

    def can_advance(self, from_gate: Gate) -> bool:
        matching = [e for e in self.exits if e.gate == from_gate]
        if not matching:
            return False
        latest = matching[-1]
        # untested sketch: real usage would also check evidence isn't a vague string
        return latest.passed and len(latest.evidence) > 20

    def audit_skipped_gates(self, target: Gate) -> list[Gate]:
        order = list(Gate)
        target_idx = order.index(target)
        completed = {e.gate for e in self.exits if e.passed}
        return [g for g in order[:target_idx] if g not in completed]
```

`audit_skipped_gates` is the useful part in an interview context — it's the mechanical check for "we're about to ship this to production and nobody ever actually validated product-market fit at MVP scale," which is exactly the RAND-documented failure mode (a third of AI projects abandoned before production, because feasibility/fit risk wasn't retired early when it was cheap to retire).

---

## How it's done in production

**Feature flags and staged rollout** are the mechanical bridge from MVP to production — rather than a hard cutover, MVP-stage code behind a flag gets progressively exposed to more traffic (canary %, then a full staged rollout) while the production-readiness dimensions above are hardened in parallel, so "production" isn't a single deploy event but a ramp with kill switches at every stage.

**Evaluation infrastructure for AI features** — the piece most traditional software staged-gate thinking doesn't cover and most AI-pilot failures trace back to: a golden dataset with known-good outputs or a graded rubric, run automatically in CI on every prompt/model/RAG-config change, with a defined regression threshold that blocks a deploy rather than being discovered from user complaints. Teams that build this at MVP stage (not bolted on post-incident) are disproportionately represented in the minority that successfully reach production, per the 2026 industry data on the pilot-to-production gap.

### Failure-mode table

| Symptom | Cause | Fix |
|---|---|---|
| POC code, hardcoded credentials and all, is still running in production 18 months later | POC's demo success created pressure to skip the rewrite under deadline | Treat POC code as explicitly non-mergeable to a production branch; budget the MVP rewrite as its own tracked work, not "polish" |
| MVP launched to a pilot cohort, usage cratered after week 2, nobody knows why | No evaluation/quality harness existed before launch, and no usage instrumentation to distinguish "quality regressed" from "feature not wanted" | Build the eval harness and basic usage analytics before MVP exit, not after |
| Production incident traces back to an edge case the prototype's "Wizard of Oz" human silently handled by hand | Prototype validated UX using a human doing the hard part; the real system never had to handle that case until production | Explicitly catalogue what the human did in the prototype and verify each case is handled (or intentionally out of scope) before MVP build starts |
| A model/prompt change silently degraded output quality for weeks before anyone noticed | No automated eval gate on AI-feature changes; quality checked by spot-check demo only | Golden-set eval harness gating every change, drift monitoring on live traffic |
| Project abandoned after months of MVP work, "nobody actually wanted this" | Prototype-stage validation was skipped or was a demo-to-leadership rather than real target-user testing | Enforce prototype exit criteria as observed user behavior, not internal approval |
| On-call has no idea how to operate the system that just went to production | Ownership/runbook dimension of the production gate was treated as optional under deadline | Make runbook + on-call rotation a hard production-gate exit criterion, not a nice-to-have |

---

## Tradeoffs & when NOT to use it

- **Don't run all four gates formally for a low-risk, reversible, internal tool.** A two-way-door decision (`T10-tech-selection`) with low blast radius doesn't need a multi-week prototype phase with formal exit criteria — build it, use it, iterate. Reserve the full staged rigor for things with real cost-of-being-wrong: customer-facing features, anything touching revenue, anything hard to unwind once real users depend on it.
- **Collapsing POC and prototype into one stage is often fine** when the technical feasibility question and the UX/value question can genuinely be tested together cheaply (a small internal tool where "can it work" and "is it useful" are answered by the same quick spike). Don't manufacture ceremony where the risk categories aren't actually separable.
- **A rigid MVP scope can become its own anti-pattern** if "minimum" gets weaponized to ship something too limited to actually test the real hypothesis — an MVP so stripped down that early users can't tell whether they'd want the real thing is not minimum-viable, it's just minimum, and it produces false-negative signal (nobody adopted it) that looks like a failed MVP exit criterion but is actually a badly-scoped MVP.
- **The AI-specific evaluation-gate addition is genuinely more process than a simple CRUD feature needs.** Don't retrofit a full golden-set eval harness onto a feature with no model/prompt-driven behavior; this addition is specifically for the failure mode where output quality can silently drift, which doesn't apply to deterministic code paths.
- **Skipping gates under real deadline pressure is sometimes the correct call, made explicitly.** The failure mode isn't skipping a gate — it's skipping a gate's *question* while quietly inheriting its risk, unacknowledged. If leadership genuinely accepts the technical-feasibility risk of going straight from POC to a production deadline, that's a legitimate, documented risk-acceptance decision (name it, get it signed off) rather than a silent scope-creep of "polish the POC a bit and call it done."

---

## Interview questions

### Q1 — What's the difference between a prototype and an MVP, precisely?
**Testing:** whether the candidate has the distinction memorized as more than a vague continuum.
**Answer:** A prototype tests whether you're building the *right thing* — UX and value proposition, in front of real target users, and is explicitly disposable, often faked underneath (a human doing the hard part manually, or mocked responses behind a real-looking UI). An MVP tests whether real users will *actually adopt and get value from* the thing at small scale, and is the first genuinely non-throwaway code in the pipeline — a real backend, real persistence, real (if minimal) infrastructure, serving a small real cohort. The prototype question is "is this the right thing"; the MVP question is "will people actually use the real version of it."
**Follow-up trap:** *"Your prototype tested well but the MVP saw zero adoption. What does that tell you?"* — most likely the prototype's "Wizard of Oz" element silently handled something the real MVP backend can't, or the prototype's small, curated user sample doesn't represent the MVP's actual launch cohort — a positive prototype signal validates the interaction concept, not the real system's ability to deliver it at even small scale, which is exactly why the MVP gate exists as a separate step rather than skipping straight to production after a good prototype.

### Q2 — Your team wants to take POC code straight to production because "it already works" and there's a deadline. What do you say?
**Testing:** whether the candidate recognizes the specific, expensive failure mode this represents.
**Answer:** POC code was deliberately built to answer one narrow technical question, with every production concern — scale, failure handling, security, observability, cost, ownership — explicitly out of scope by design; "it already works" is true only for the narrow case the POC tested, usually a small hand-picked sample with no adversarial input and no real load. Taking it straight to production doesn't skip the work those dimensions require, it just means production discovers the gaps live, which is a materially more expensive place to discover them than a design review. If the deadline is truly immovable, that's a legitimate, explicit risk-acceptance conversation with whoever owns that risk — not a silent decision to skip the hardening work.
**Follow-up trap:** *"What if I told you we don't have time for either the hardening work or an explicit risk conversation?"* — then you don't have time to ship safely, and the honest answer is to say that plainly rather than let the deadline silently absorb the risk — naming the specific things that will break (which failure modes are untested, what the actual cost/scale assumptions are) gives leadership a real choice instead of an uninformed one, even under time pressure.

### Q3 — What does the RAND 2025 finding on AI project failure actually break down into, and why does it matter for how you'd structure a pilot?
**Testing:** whether the candidate has engaged with real current data, not just folk wisdom about "AI is hard."
**Answer:** RAND found 80.3% of AI projects fail to deliver intended business value, split three ways: 33.8% abandoned before ever reaching production, 28.4% reach production but underdeliver, and 18.1% deliver some value but can't justify their cost. The 33.8%-abandoned-before-production figure is the most actionable one for pilot structure — it means a third of failures are exactly the kind the POC/prototype gates exist to catch cheaply, and their still happening at that scale means those early gates are either being skipped or being run without real exit criteria (a demo to leadership standing in for actual user-behavior evidence).
**Follow-up trap:** *"Doesn't that number argue for skipping AI pilots entirely and going straight to a smaller, cheaper bet?"* — the opposite: it argues for taking the early gates (POC's technical feasibility, prototype's real-user validation) more seriously and more cheaply, specifically because a third of the failures are ones those gates are supposed to catch before the expensive part starts. The lesson from the data is "the gates aren't being run rigorously enough," not "the gates don't work."

### Q4 — What's specifically different about production-readiness for an AI/LLM-backed feature versus a traditional CRUD feature?
**Testing:** the AI-specific addition to the classic four-gate model.
**Answer:** All the traditional production dimensions still apply (scale, resilience, observability, security, cost, ownership), plus one that traditional software's deterministic code paths don't need: an automated evaluation harness — a golden set of inputs with known-good outputs or a graded rubric — gating every model, prompt, or retrieval-config change, because output quality can silently drift in ways a traditional test suite (which checks for correctness, not quality-on-a-spectrum) wouldn't catch. Drift monitoring on live production traffic is the ongoing analog once shipped, since the input distribution itself can shift after launch in ways that degrade quality without any code change at all.
**Follow-up trap:** *"Isn't a golden-set eval just a regular test suite with extra steps?"* — no, meaningfully different: a regular test suite asserts binary correctness (does this function return the right value), while an eval harness for generative output usually grades against a rubric or similarity threshold because there's often no single "right" answer, only better/worse ones — and it needs to be re-run not just on code changes but on prompt changes, model version changes, and even upstream data changes, none of which a traditional CI test suite is triggered by.

### Q5 — Walk me through the exit criteria you'd set for each of the four gates for a new AI-powered search feature.
**Testing:** whether they can operationalize the framework on a concrete example, with real measurable criteria.
**Answer:** POC (days): a notebook script measuring retrieval latency and relevance on 10-20 hand-picked queries against a corpus sample — exit when latency and relevance numbers clear a rough bar, e.g. "p50 under 500ms, relevant result in top-5 for 8/10 queries." Prototype (1-2 weeks): a real-looking search UI with possibly mocked/curated results shown to 6-10 target users, exit on observed task success — "6/8 completed their search task and preferred it to current search." MVP (4-8 weeks): a real backend with real indexing serving a small pilot cohort, with a golden-set eval harness already gating changes, exit on real usage — "60% weekly-active among 50 pilot users after 4 weeks, unit cost per query under $X." Production: no single exit criterion — ongoing SLOs (latency, availability, eval-harness pass rate) with defined on-call ownership.
**Follow-up trap:** *"Your MVP pilot cohort loved it, but production rollout to the full user base saw much lower engagement. Why might the gate have missed this?"* — pilot cohorts are frequently self-selected (early adopters, more tolerant of rough edges, sometimes internal or friendly users) and don't represent the full population's needs, tech-savviness, or query patterns — MVP exit criteria measured on a non-representative cohort can pass while masking a mismatch that only shows up at real scale, which argues for pilot-cohort selection being itself a deliberate, examined choice rather than "whoever we could get."

### Q6 — What's a "Wizard of Oz" prototype and when is it the right call?
**Testing:** knowledge of a specific, real prototyping technique and its tradeoff.
**Answer:** A prototype where a human manually performs the function the eventual system would automate, behind an interface that looks real to the test user — used specifically to validate the UX and value proposition of an interaction before investing in building the (often expensive, often AI-driven) backend that would actually deliver it. Right call when the backend is expensive or slow to build relative to the UX risk being tested, and when a human can plausibly simulate the eventual output quality closely enough for the test to be meaningful.
**Follow-up trap:** *"What's the biggest risk this technique introduces into your MVP planning?"* — the human doing the work by hand can silently handle edge cases, ambiguity, and quality bars that the real automated system won't be able to match, so a successful Wizard-of-Oz prototype validates the *concept* but tells you nothing about whether the real system can achieve the same quality — the MVP build needs to explicitly catalogue what the human did and verify the real system handles each case, or the MVP will underdeliver relative to what the prototype demonstrated.

### Q7 — Someone argues MVP and production are the same thing, just "more polished." Do you agree?
**Testing:** whether they see the qualitative, not just quantitative, difference between the two stages.
**Answer:** No — the difference isn't degree of polish, it's which risks have been retired. MVP retires market/adoption risk (will real users want this) with a small, often hand-held cohort and informally-tracked operations. Production retires operational/scale risk (will this hold up under real load, real failure, real adversarial input, with people other than the original builders able to run it) — that requires structurally different things (resilience patterns, on-call ownership, tested rollback, capacity planning), not just a nicer UI or fewer bugs on the same code path. A system can be extremely "polished" in its narrow MVP happy path and still catastrophically fail production readiness because nobody ever built the failure-mode handling that only matters at real scale.
**Follow-up trap:** *"Give a concrete example where polishing the MVP would NOT get you to production-ready."* — an MVP with a beautifully polished UI, zero bugs in the pilot cohort's usage patterns, but no rate limiting, no circuit breaker on its one external dependency, and a single Postgres instance with no read replica — polish the UI further and none of that changes; the production-readiness gap is structural, in dimensions the MVP never had reason to build.

### Q8 — Staff-level: leadership wants to skip the prototype stage entirely for a new AI feature to "move fast." How do you respond?
**Testing:** judgment about when gate-skipping is a legitimate call versus a documented risk being silently absorbed.
**Answer:** First separate the two things "move fast" could mean: compressing the *time* spent at the prototype stage (legitimate — a prototype can be days, not weeks, if the UX question is narrow) versus skipping the *question* the prototype stage answers (risky — you're betting the MVP build investment on an unvalidated assumption about what users actually want). If the underlying product/UX risk is genuinely low (an internal tool, a well-understood user need, a close analog already validated elsewhere), skipping is defensible. If it's a genuinely novel interaction for an external, revenue-relevant audience, skipping it is exactly the kind of decision RAND's data shows failing at scale — name that tradeoff explicitly to leadership rather than silently complying or silently resisting.
**Follow-up trap:** *"What's the fastest legitimate way to retire prototype-stage risk without a formal multi-week phase?"* — a 2-3 day Wizard-of-Oz or clickable-mockup test with 5-6 real target users, which is enough to catch a fundamentally wrong direction (the single most expensive failure mode this stage exists to catch) even though it won't catch every UX nuance — "fast" and "zero" are different things, and the fast version is almost always available if the team is willing to spend a few days rather than zero.

---

## Red flags that fail you

- Treating POC code as directly upgradeable to production because "it already works," without acknowledging every production dimension it was deliberately built to skip.
- Setting a stage's exit criteria as "the demo went well" instead of a specific, measured, observed outcome.
- Not knowing any current statistics on the AI pilot-to-production gap when the conversation is explicitly about AI features.
- Describing production-readiness as "more testing" rather than naming the specific dimensions that structurally change (resilience, observability, ownership, cost accounting, rollback).
- Treating MVP and production as the same code at different polish levels.
- For an AI feature, having no answer to "how do you know quality didn't silently regress" beyond "we'd notice."
- Skipping a gate under deadline pressure without naming, explicitly, which risk is being silently inherited.

---

## Cheat card

```
POC          days-2wk   Q: can this be built at all?          throwaway, no UI/scale/auth
                         exit: specific technical yes/no w/ evidence numbers

PROTOTYPE    1-3wk       Q: is this the right thing to build?  throwaway, real target users
                         often "Wizard of Oz" (human fakes backend)
                         exit: observed user behavior (X/N completed task, preferred it)

MVP          wk-2mo      Q: will real users adopt this,        FIRST non-throwaway code
                            small scale?                       real (if minimal) backend/auth/obs
                         AI-specific: golden-set eval harness must exist BEFORE exit
                         exit: real usage/retention numbers from real cohort, real time window

PRODUCTION   ongoing     Q: holds up at real load/failure/     ongoing SLOs, not a one-time gate
                            cost/ops, indefinitely?
  changes from MVP: scale(load-tested) · resilience(full catalogue) ·
  observability(traces/alerts/on-call) · security(least-priv) ·
  data(backup tested) · cost(modeled, owned) · rollback(automated, staged)·
  AI: drift monitoring + eval gate on every model/prompt change

STATS (know cold)   RAND 2025: 80.3% of AI projects fail to deliver value
                     → 33.8% abandoned pre-production · 28.4% underdeliver · 18.1% cost-unjustified
                     March 2026 survey: 78% enterprises have AI pilots, only 14% scaled org-wide
                     MIT-associated: ~95% of enterprise AI pilots show zero P&L impact
                     root cause (per multiple 2026 analyses): ORGANIZATIONAL not model capability
                     (data readiness, unclear ownership, missing eval infra, change mgmt)

FAILURE MODE TO NAME  skipping a gate's QUESTION while reusing its CODE — the risk doesn't
                       disappear, it just gets discovered later, more expensively
```

## Sources

- [From AI Pilot to Production: Why 80% of Enterprise AI Stalls in 2026 — webpuppies.com.sg](https://webpuppies.com.sg/ai-pilot-to-production-enterprise-2026/) — accessed 2026-08-02
- [AI Agent Scaling Gap March 2026: Pilot to Production — digitalapplied.com](https://www.digitalapplied.com/blog/ai-agent-scaling-gap-march-2026-pilot-to-production) — accessed 2026-08-02
- [AI Project Failure Rate in 2026: What the Data Shows — Folio3 AI](https://www.folio3.ai/blog/ai-project-failure-rate-stats) — accessed 2026-08-02
- [Why 88% of Enterprise AI Pilots Never Reach Production — Institute PM](https://www.institutepm.com/knowledge-hub/why-enterprise-ai-pilots-fail) — accessed 2026-08-02
- [Prototype vs MVP vs Proof of Concept: Key Differences Explained (2026) — UXPin](https://www.uxpin.com/studio/blog/prototype-vs-mvp-vs-proof-of-concept/) — accessed 2026-08-02
- [Enterprise AI Deployment Gap: Why Pilots Fail to Reach Production — VaaSBlock](https://www.vaasblock.com/news/enterprise-ai-deployment-gap-pilots-vs-production-2026/) — accessed 2026-08-02

## Changelog
- 2026-08-02 — created
