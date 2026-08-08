# Choosing the Right System: Decision Frameworks, Scorecards, Reversible vs One-Way Doors, Build-vs-Buy

> **Track:** T10 System Design · **Time:** 2.5h · **Prereqs:** `T10-design-method` · **Updated:** 2026-08-02
> **Module id:** `T10-tech-selection` · **Tags:** craft, critical

## The 30-second version

Technology selection is a decision-quality problem before it's a technical one: classify the decision as reversible ("two-way door" — cheap to undo, decide fast, decide at the lowest competent level) or irreversible ("one-way door" — expensive or impossible to undo, decide slowly, decide with more input and more documented reasoning), then run a lightweight weighted scorecard against 4-6 criteria that actually matter for *this* decision (not a generic checklist), and write it down as an ADR that names the alternatives you rejected and why, not just the winner. Build-vs-buy collapses to one question: does this capability touch your actual differentiation (revenue, retention, or a defensible moat), or is it undifferentiated plumbing everyone needs the same version of? Differentiating capability, lean toward build; undifferentiated plumbing, lean toward buy — you are not going to out-execute a vendor who's spent a decade on edge cases in something that isn't your product. The interview signal is not "which technology did you pick" — it's whether you can defend a pick under adversarial questioning about the ones you didn't choose.

## Why this gets asked

Because "we chose Kafka" is a sentence anyone can say, and it tells the interviewer nothing about judgment. What they've lived through is a technology chosen for the wrong reason — resume-driven development, a conference talk, a vendor's sales deck, "it's what we know" — that became an expensive one-way door two years later: a database that couldn't scale the way the team assumed, a managed service that locked them into a vendor's roadmap, a framework abandoned by its maintainers. They want to see whether you distinguish decisions worth agonizing over from decisions worth making fast, whether your evaluation criteria are specific to the problem rather than generic, and whether you can hold your ground on a choice when someone senior pushes back with a plausible-sounding but wrong alternative.

---

## Lineage: past → present → future

**What came before.** Early technology selection in most organizations was informal — "the architect decides," or "whoever's been here longest picks," with reasoning that lived in someone's head and evaporated when they left. The pain this caused was rediscovered constantly: a system built on a technology choice nobody could explain, with no record of what was considered and rejected, so every re-litigation of the decision started from zero. Michael Nygard's 2011 blog post introducing Architecture Decision Records gave this a name and a lightweight format specifically to fix "we don't remember why we did this" — a direct reaction to watching decisions get re-argued by people who weren't in the original room. Jeff Bezos's 2015 shareholder letter formalized "one-way door vs two-way door" as vocabulary for decision *speed*, which was a separate but related problem: organizations were spending the same deliberation time on decisions that cost nothing to reverse as on ones that were nearly impossible to undo, which is itself a resource-allocation failure.

**Where it stands now.** ADRs are now genuinely mainstream practice at engineering orgs with any staff+ discipline — lightweight, per-repo, one file per significant decision, superseded rather than edited when circumstances change. The live disagreement is scope creep: some teams write an ADR for every dependency bump, which defeats the purpose (signal drowns in noise) — the accepted discipline is to reserve ADRs for decisions that are architecturally significant, hard to reverse, or cross-cutting, and skip them for anything a single PR review can catch and undo. On build-vs-buy, the frontier-model era reframed the question specifically for AI/ML capabilities: "build or buy" as a binary is now widely considered the wrong framing at the enterprise level; the actual question is which *layer* you own (infrastructure, model, orchestration, UX) versus which you delegate, because most real systems are a blend across those layers rather than a single build-or-buy verdict for "the AI system." What's actually deployed: buy systems-of-record and compliance-heavy plumbing (auth, billing, payroll) where a vendor has already paid down a decade of edge cases; build the layer that's actually your differentiation (the specific agent workflow, the specific ranking model, the product experience).

**Where it's heading.** Reversibility itself is getting harder to assess in AI-system decisions, and this is a genuine, not-yet-settled shift: the same 2026 industry writing that reframed build-vs-buy also notes that decisions once assumed reversible (swap one model API for another) are turning out to have hidden one-way-door costs — fine-tuning data, prompt engineering investment, and evaluation harnesses built around one vendor's specific behavior don't transfer cleanly, so a "just swap the API" decision can be more like a one-way door than it looks on the surface. Expect more explicit frameworks scoring *switching cost* as its own axis, separate from initial capability fit, rather than assuming API-compatible services are interchangeable. Treat "AI vendor lock-in via evaluation and fine-tuning investment, not just API surface" as a real and growing consideration, still being actively worked out industry-wide rather than a solved methodology.

---

## Mental model

Two orthogonal axes decide how much process a technology decision deserves — reversibility (how expensive to undo) and blast radius (how many people/systems it touches). Most of the actual craft is correctly placing a decision on this grid before debating the merits of any specific option.

```
                    HIGH BLAST RADIUS
                           │
      "decide carefully,   │   "decide carefully,
       document it, get    │    document it, get
       buy-in — but you    │    buy-in, and consider
       CAN undo it if      │    a reversible trial
       wrong"              │    first if at all possible"
                           │
   REVERSIBLE ─────────────┼───────────────── ONE-WAY DOOR
   (cheap to undo)         │              (expensive/impossible to undo)
                           │
      "just decide.        │   "still decide fast if
       lowest competent    │    blast radius is small —
       level, no ADR       │    a single team's internal
       needed"             │    tool choice with no data
                           │    lock-in is still low-stakes"
                           │
                    LOW BLAST RADIUS
```

Primary database engine, core message bus, the model provider your evaluation harness is built around, the auth/identity provider users are enrolled in — high blast radius, expensive to undo, deserves a scorecard and an ADR. A team's internal choice of task-queue library for a non-critical batch job, a linter, a logging format — low blast radius, cheap to undo, deciding fast and moving on is the correct amount of process. The single most common interview trap is treating every technology decision with the same weight regardless of quadrant.

---

## How it actually works

### 1. Classify: reversible or one-way door, and why

Ask three questions, in order:

1. **Data/state lock-in** — does adopting this create data, schemas, or trained artifacts (fine-tuned models, prompt/eval harnesses tuned to one vendor's quirks) that don't migrate cleanly to an alternative? If yes, lean one-way door regardless of how "swappable" the interface looks.
2. **Organizational lock-in** — does adopting this require team retraining, hiring against it, or process changes that are themselves expensive to unwind (a new deployment pipeline, a new on-call rotation shape)? If yes, the decision is harder to reverse than the technology alone suggests.
3. **Blast radius** — how many other systems, teams, or customer-facing behaviors depend on this choice being stable? A database engine underneath twelve services is a different decision than a database engine underneath one internal reporting job.

**The trap interviewers set:** presenting a decision that *looks* reversible on the surface (any API-compatible message queue, any API-compatible LLM provider) and asking you whether it's actually a two-way door. The correct answer interrogates data/state and organizational lock-in explicitly rather than accepting interface compatibility as proof of reversibility — this is exactly the 2026 AI-vendor lock-in pattern: swapping the model API is easy, but the fine-tuning data, few-shot examples, and eval suite built around one provider's specific output distribution often aren't.

### 2. Build the scorecard — specific to this decision, not generic

A generic checklist ("scalability, cost, community support, ease of use...") produces a generic, defensible-sounding but ultimately arbitrary score, because every option scores "fine" on generic criteria. The craft is deriving 4-6 criteria from the *actual constraints of this decision* — usually pulled directly from the requirements-gathering step of the design method (`T10-design-method`).

```
Weighted scorecard — pick ONE database for a new service, 3 candidates

Criterion                          Weight   PostgreSQL   DynamoDB   ClickHouse
────────────────────────────────────────────────────────────────────────────
Query pattern fit                    30%        8            4          9
  (heavy ad-hoc joins + range scans
   on a 200M-row analytics table)
Team's existing operational depth    20%        9            5          3
  (2 engineers know Postgres well,
   zero DynamoDB/ClickHouse experience)
Cost at projected scale (18mo)       20%        7            6          9
  (200M rows, 5k QPS read, 500 QPS write)
Consistency requirement              15%        9            6          6
  (financial ledger entries, needs
   strict read-after-write)
Migration/exit cost if wrong         15%        8            3          5
  (standard SQL, portable schema
   vs vendor-specific data model)
────────────────────────────────────────────────────────────────────────────
Weighted total                                7.75         4.75       6.95
```

`weighted_total = Σ(weight × score)`. PostgreSQL wins here specifically *because* of this decision's constraints (join-heavy queries, existing team depth, a consistency requirement) — change the constraints (pure key-value access pattern, a team already deep in DynamoDB, no join requirement) and the same scorecard structure produces a different winner. That's the point: the scorecard's value is forcing explicit, numbered tradeoffs rather than a vibes-based pick, and it's falsifiable — anyone can challenge a specific weight or score and the disagreement becomes concrete instead of "I just think X is better."

**Known failure mode of scorecards:** reverse-engineering the weights to justify a pick you'd already made. The tell, in an interview or in a real review, is a scorecard where the "winning" option happens to score highest on every criterion — real tradeoffs produce a mixed picture, where your chosen option loses on 1-2 criteria and wins on the ones you decided (explicitly, beforehand) mattered most.

### 3. Build vs. buy vs. assemble

Three options, not two, and increasingly a fourth (acquire) at the enterprise scale, but for most engineering decisions it's:

| Option | When it's right | Concrete cost you're accepting |
|---|---|---|
| **Buy** (managed service / vendor / SaaS) | Undifferentiated capability — auth, payments, email delivery, observability platforms, most databases-as-a-service | Vendor risk (pricing changes, roadmap divergence, acquisition), data-egress/lock-in cost, ongoing dependency on their reliability |
| **Build** | The capability *is* your differentiation, or no vendor solves your specific constraint at acceptable cost/risk | Ongoing engineering cost, the team becomes the on-call for something a vendor would otherwise own, opportunity cost of not building the differentiating thing instead |
| **Assemble/OSS** | Middle ground — well-understood building blocks (Kafka, Postgres, Kubernetes) that are commoditized enough that "build" doesn't mean starting from nothing, but not so undifferentiated that a managed SaaS is a clean fit | Operational burden shifts to your team (you run it), but you avoid both vendor lock-in and the cost of inventing the primitive itself |

**The actual test, stated as a single question:** does this capability touch revenue, retention, margin, or a defensible moat? If yes, building (or deeply customizing OSS) is usually worth the ongoing cost, because a vendor's generic solution can't embody your specific competitive edge and you don't want your differentiation on someone else's roadmap. If no — it's plumbing every company in your position needs the same version of — buying is almost always cheaper over any reasonable time horizon than the fully-loaded cost of building and then operating it forever, including the opportunity cost of the engineers who'd otherwise work on the differentiating thing.

### 4. Defending a choice under pressure — the actual interview skill

The scorecard and the ADR are preparation; the interview (and the real design review) tests whether you can hold the reasoning under adversarial questioning without either caving reflexively or getting defensive. The mechanical pattern that works:

1. **Restate the constraint that drove the decision**, not the decision itself — "given the consistency requirement on the ledger table, and the team's zero prior DynamoDB experience, here's why Postgres scored highest," not "Postgres is just better."
2. **Name what would change your mind**, concretely — "if write volume were 10x what we project, or if we had two engineers with production DynamoDB depth, this scorecard tips the other way — here's the number where that happens." A decision you can't imagine ever reversing under any new evidence is a decision you haven't actually reasoned about; it's a preference.
3. **Concede the real tradeoff explicitly** rather than defending the choice as flawless — "yes, this is worse on X, and here's why we decided X mattered less than Y for this specific system." Conceding a genuine weakness while holding the overall conclusion is a stronger signal than defending every dimension, which reads as advocacy rather than judgment.

---

## Build it from scratch

A minimal, reusable scorecard-plus-ADR generator — useful to have runnable, not just describable, because "walk me through how you'd structure this" is a common follow-up:

```python
from dataclasses import dataclass, field

@dataclass
class Criterion:
    name: str
    weight: float          # must sum to 1.0 across all criteria
    rationale: str          # WHY this criterion matters for THIS decision

@dataclass
class Candidate:
    name: str
    scores: dict[str, float]   # criterion name -> 0-10 score
    notes: dict[str, str] = field(default_factory=dict)  # evidence per score

def weighted_total(candidate: Candidate, criteria: list[Criterion]) -> float:
    return sum(c.weight * candidate.scores[c.name] for c in criteria)

def is_one_way_door(data_lockin: bool, org_lockin: bool, blast_radius: str) -> bool:
    # untested sketch — real usage requires judgment, not just these three booleans
    return data_lockin or org_lockin or blast_radius == "high"

def render_adr(decision: str, criteria: list[Criterion], candidates: list[Candidate],
               chosen: str, reversible: bool) -> str:
    lines = [f"# ADR: {decision}", "", "## Status: Accepted", "",
             f"## Reversibility: {'two-way door' if reversible else 'ONE-WAY DOOR — decided deliberately slowly'}",
             "", "## Criteria considered"]
    for c in criteria:
        lines.append(f"- **{c.name}** (weight {c.weight}): {c.rationale}")
    lines.append("\n## Scorecard")
    for cand in candidates:
        total = weighted_total(cand, criteria)
        marker = " <- CHOSEN" if cand.name == chosen else ""
        lines.append(f"- {cand.name}: {total:.2f}{marker}")
    lines.append("\n## What would change this decision")
    lines.append("(fill in: the specific metric/threshold that would flip the scorecard)")
    return "\n".join(lines)
```

The point of formalizing this isn't the code — it's that a scorecard without explicit rationale per criterion and an explicit "what would change this" section is indistinguishable from a rationalized pre-existing preference, and a good interviewer will find that gap in about two follow-up questions.

---

## How it's done in production

**ADR format** — the widely-adopted lightweight template (Nygard's original, still the base most teams customize): Title, Status (proposed/accepted/superseded), Context (the forces at play, including constraints that aren't purely technical — deadline, team skill, budget), Decision, Consequences (both the ones you wanted and the ones you're accepting), and — the part most teams skip and shouldn't — **Alternatives considered**, each with why it was rejected. Stored in-repo (`/docs/adr/NNNN-title.md`), one file per decision, never edited after acceptance — superseded by a new ADR that links back, so the history of reasoning stays intact even after the decision changes.

**Where this breaks down in practice:**

| Symptom | Cause | Fix |
|---|---|---|
| Every dependency bump gets an ADR, nobody reads them anymore | No filter on "architecturally significant" | Reserve ADRs for decisions that are hard to reverse, cross-cutting, or set a precedent; a single-PR-reversible choice doesn't need one |
| The "losing" options in the scorecard all score suspiciously low across the board | Weights/scores reverse-engineered to justify a pre-made decision | Require the chosen option to concede at least one criterion; get scores reviewed by someone who'd genuinely have picked differently |
| A decision documented as "reversible" turns out to cost 6 months to undo | Data/state or organizational lock-in wasn't assessed, only API-surface compatibility | Explicitly score switching cost (data migration, retraining, eval-harness rebuild) as its own criterion, especially for AI vendor/model choices |
| Nobody can find why a 2-year-old decision was made | No ADR was written, or it lives in a deleted Slack thread | Make ADR-on-merge a checklist item for anything touching the architecturally-significant list, enforced in PR template, not just convention |
| The same build-vs-buy debate happens every 6 months with the same people re-litigating from scratch | No documented "what would change this decision" threshold | ADR's consequences section should state the concrete trigger for revisiting, so re-litigation only happens when that trigger fires |

---

## Tradeoffs & when NOT to use it

- **Don't scorecard a decision that's obviously low-stakes and reversible.** The overhead of building criteria, weights, and a written ADR for choosing a logging library for one internal batch job is process for its own sake — decide fast, at the lowest competent level, and move on. Reserve the ceremony for the top-right quadrant of the mental-model grid.
- **Don't treat "reversible" as a synonym for "cheap right now."** Some decisions are reversible in principle but expensive enough to reverse in practice (a database migration is technically always possible) that they deserve one-way-door-level deliberation even though nothing is literally permanent. Use expected cost-to-reverse, not a binary possible/impossible.
- **A scorecard is not a substitute for judgment on criteria you can't quantify.** Team morale, hiring market perception, and political capital with a key stakeholder are real inputs to some technology decisions and don't fit neatly into a 0-10 score — naming them explicitly as unscored factors is more honest than forcing a number onto something you're actually guessing at.
- **Build-vs-buy's "does it touch differentiation" test breaks down for genuinely novel categories** where there's no vendor maturity yet to buy from at any price — early in the AI-agent tooling wave, teams that wanted to buy an "agent evaluation platform" in 2023 often couldn't, because nothing adequate existed, making "build" the only option regardless of whether it was core differentiation. Revisit build decisions as the vendor market matures; a build decision made when there was no alternative isn't necessarily still correct two years later.
- **Don't let "we can always change it later" justify skipping the switching-cost analysis for AI/ML vendor choices specifically.** The 2026-era lesson is that fine-tuning data, prompt engineering investment, and evaluation harnesses tuned to one provider's output distribution create real lock-in even when the API surface looks interchangeable — treat model/vendor choice in an AI system as closer to a one-way door than the interface compatibility suggests, unless you've deliberately kept the eval harness and prompts provider-agnostic from day one.

---

## Interview questions

### Q1 — What's the difference between a one-way door and a two-way door decision, and how does that change how you make it?
**Testing:** baseline vocabulary and whether they connect it to actual process differences, not just definitions.
**Answer:** A two-way door is cheap to reverse — decide fast, at the lowest competent level, without extensive process, because the cost of being wrong is low. A one-way door is expensive or impossible to reverse — worth slowing down for, getting more input, documenting the reasoning (an ADR), and considering a smaller reversible trial first if one exists. The practical shift: most organizational dysfunction here is applying one-way-door process to two-way-door decisions (analysis paralysis on low-stakes choices) or the reverse (rushing a genuinely hard-to-reverse choice because "we can always change it later" when it can't actually be changed cheaply).
**Follow-up trap:** *"Give me a decision that looks reversible but isn't."* — swapping an LLM API provider looks like a two-way-door interface swap, but fine-tuning data, few-shot prompts, and an evaluation harness built around one provider's specific output distribution don't transfer cleanly — the real switching cost is in the accumulated investment around the interface, not the interface itself.

### Q2 — Walk me through how you'd build a weighted scorecard for choosing between two databases.
**Testing:** whether the criteria come from this decision's actual constraints or from a generic checklist.
**Answer:** Start from the requirements already gathered in the design phase — query patterns, consistency needs, scale projections, team's existing operational depth — and derive 4-6 criteria specific to those, not a generic "scalability/cost/community" list every option scores "fine" on. Weight them by how much each actually matters for this system (a financial ledger weights consistency heavily; an analytics dashboard weights query flexibility and cost). Score each candidate 0-10 per criterion with a one-line evidence note, compute the weighted sum, and expect the winner to lose on at least one criterion — a scorecard where the chosen option wins everything is a sign the weights were reverse-engineered.
**Follow-up trap:** *"Your scorecard shows Postgres beating DynamoDB by 3 points overall. How confident should I be in that number?"* — not very, taken alone — the scorecard's value isn't the precision of the arithmetic, it's that it forces explicit, challengeable tradeoffs. Say plainly that the number is a communication and debate tool, not a proof, and that a 3-point gap with soft, judgment-based scores on some criteria is well within the noise of "reasonable people could weight this differently."

### Q3 — When is buying clearly better than building, and when is that reversed?
**Testing:** the differentiation test, applied concretely rather than as a slogan.
**Answer:** Buy when the capability is undifferentiated plumbing that every company in your position needs the same version of — auth, payments processing, email deliverability, most infrastructure-as-a-service — because a vendor has already paid down a decade of edge cases you'd otherwise rediscover one incident at a time. Build when the capability directly touches revenue, retention, margin, or a defensible competitive moat, because a generic vendor solution structurally can't embody your specific edge, and putting your differentiation on someone else's roadmap is a strategic risk independent of the technology's quality.
**Follow-up trap:** *"Your CFO says building is always more expensive than a SaaS subscription — counter that."* — true for the sticker price alone, false as a total-cost comparison once you include the compounding cost of *not* differentiating: a vendor's roadmap moves at their priorities, and if the capability is core to your product, every quarter you're waiting on their feature request queue is a quarter a competitor building it in-house can move faster. The right comparison is fully-loaded build cost (including ongoing ops) against the strategic cost of ceding control of a differentiating capability, not sticker price against sticker price.

### Q4 — Your team wants to write an ADR for every dependency version bump. Good idea?
**Testing:** whether the candidate can push back on over-application of a good practice.
**Answer:** No — that defeats the purpose. ADRs exist to preserve reasoning for decisions that are architecturally significant, hard to reverse, or set a precedent other decisions will reference; a routine dependency bump a single PR review can catch and revert doesn't need one. Writing one for everything drowns the signal — nobody reads a hundred ADRs to find the three that actually matter, so the practice degrades into ceremony and eventually gets abandoned altogether, taking the useful cases down with it.
**Follow-up trap:** *"Where exactly is the line?"* — roughly: does reversing this require more than a single team's coordinated effort, does it lock in data/schema/vendor-specific behavior, or will someone reasonably ask "why did we do this" more than six months from now? Any yes, write it up; if it's a same-team, same-sprint, trivially-revertable change, skip it.

### Q5 — You picked technology X eighteen months ago; a new hire challenges it in a design review, arguing for Y. How do you handle it?
**Testing:** whether the candidate defends reasoning without either steamrolling or capitulating reflexively.
**Answer:** Restate the constraint that drove the original decision (not just the decision), pull up the ADR if one exists — that's exactly what it's for — and check whether the constraint has actually changed since then (scale, team composition, requirements) or whether the new hire is arguing from a preference that doesn't account for context they weren't in the room for. If the constraint changed, the original decision may genuinely be wrong now and revisiting is correct. If it hasn't, explain the specific tradeoff that made X win over Y at the time, concede honestly where Y is genuinely better, and hold the conclusion if the reasons it lost still apply.
**Follow-up trap:** *"What if you don't have an ADR and genuinely can't remember why?"* — say so directly rather than inventing a post-hoc justification, and treat the absence of documented reasoning as itself the finding: re-run a scorecard now with current constraints rather than defending a decision neither you nor anyone else can actually reconstruct the reasoning for. Pretending certainty you don't have is worse than admitting the gap.

### Q6 — What's wrong with using the same 10-criterion generic checklist (scalability, cost, ease of use, community, docs, security...) for every technology decision?
**Testing:** whether they see genericness as the actual failure mode of bad scorecards.
**Answer:** Generic criteria are ones every mature option scores "fine" on, so the total ends up dominated by noise or by whichever criteria happen to have the biggest score spread rather than the ones that actually matter for this system. The fix is deriving criteria from the specific constraints of the decision at hand — the actual query pattern, the actual team's depth, the actual scale number, the actual consistency requirement — which is exactly the requirements-gathering step of the design method applied to the decision itself, not the system.
**Follow-up trap:** *"Doesn't that make every scorecard bespoke and impossible to compare across decisions?"* — yes, and that's correct, not a flaw — technology decisions aren't comparable to each other in the way the criteria need to be; what should be reusable is the *process* of deriving criteria from constraints and requiring a documented rationale per weight, not a fixed criteria list applied uniformly.

### Q7 — Describe a build-vs-buy decision you'd expect to have to revisit, and what would trigger the revisit.
**Testing:** whether they think about decisions as having a shelf life, not a permanent verdict.
**Answer:** Any "build" decision made because no adequate vendor existed at the time — early AI-agent evaluation tooling in 2023 is the canonical example, where teams built in-house eval harnesses because nothing mature existed to buy. The trigger to revisit: the vendor market matures to the point where a purchased solution now matches or exceeds the in-house build's capability at a lower total cost, which should be checked periodically (annually, or on a specific cost/capability threshold) rather than assumed to never happen just because the original decision was correct when made.
**Follow-up trap:** *"Your in-house build now has two years of tuning specific to your data. Doesn't that switching cost argue against ever revisiting?"* — that's a real cost to weigh, not an automatic veto — the question becomes whether the vendor's now-mature offering plus a migration cost beats the ongoing maintenance burden of the in-house system over the next few years, which is exactly the kind of concrete threshold that belongs in the original ADR's "what would change this decision" section.

### Q8 — How do you evaluate "switching cost" for an AI/ML vendor decision specifically, differently from a traditional infrastructure vendor?
**Testing:** whether they've engaged with the AI-specific lock-in pattern, not just generic vendor lock-in.
**Answer:** Traditional infrastructure switching cost is mostly data migration and API rewiring — real but usually boundable. AI/ML vendor switching cost includes that plus fine-tuning data and any model customization (which often doesn't transfer to a different provider's architecture at all), prompt engineering tuned to one model's specific instruction-following quirks, and an evaluation harness whose golden answers and rubrics were built around one provider's output distribution — all three of which represent real, hard-to-quantify sunk investment that doesn't show up if you only assess "is the API interface swappable."
**Follow-up trap:** *"How would you have designed the system 18 months ago to make this switching cost lower, knowing what you know now?"* — keep the evaluation harness and prompt library provider-agnostic from day one (abstract the model call behind an interface, run the same golden-set evals against any candidate model, avoid encoding provider-specific quirks into prompts where a more portable phrasing exists) — treating model choice as a two-way door requires deliberately engineering for that reversibility up front, it doesn't come for free from using a REST API.

### Q9 — A colleague says "just use what we already know, switching technologies is always a waste of time." How do you respond?
**Testing:** whether the candidate can articulate when familiarity is and isn't the right criterion.
**Answer:** Familiarity is a legitimate, real criterion — it belongs in the scorecard as "team's existing operational depth," often weighted significantly, because operating something the team has never run in production is a genuine risk independent of the technology's merits. But it's one criterion among several, not an automatic veto — if the query pattern or scale requirement is fundamentally mismatched to the familiar tool, "we already know it" doesn't fix that mismatch, it just defers the pain to whoever's on call when it breaks under load the familiar tool was never designed for.
**Follow-up trap:** *"So when does familiarity alone decide it?"* — when the other criteria are genuinely close (the scorecard's non-familiarity criteria produce similar scores across candidates) — at that point, familiarity is a legitimate tiebreaker, because the operational risk reduction from known tooling outweighs a marginal technical edge from an unfamiliar alternative. It's a tiebreaker, not the first criterion you check.

### Q10 — Staff-level: your VP wants a single technology-selection framework mandated across a 200-engineer org. What do you push back on, and what do you keep?
**Testing:** organizational judgment about process standardization versus decision-specific reasoning.
**Answer:** Keep: the requirement that architecturally-significant, hard-to-reverse decisions get a written ADR with alternatives considered, and the discipline of classifying reversibility before debating options — those generalize cleanly across teams and decisions. Push back on: a single fixed scorecard criteria list mandated org-wide, because the whole value of a scorecard is deriving criteria from the specific decision's constraints; a generic mandated list produces exactly the noise-dominated, comparable-looking-but-meaningless scores this framework is supposed to prevent. Propose instead: mandate the *process* (classify reversibility, derive decision-specific criteria, document alternatives and rationale, name what would change the decision) without mandating specific criteria or weights.
**Follow-up trap:** *"How do you get 200 engineers to actually follow a process instead of a checklist, without a checklist to enforce?"* — bake the minimum structural requirement into the ADR template itself (sections for reversibility classification, criteria-with-rationale, alternatives considered, what-would-change-this) so the *shape* is enforced by the template even though the *content* is decision-specific — enforce structure, not substance, at the org level; let teams own substance.

---

## Red flags that fail you

- Treating every technology decision with the same process weight regardless of reversibility or blast radius.
- Presenting a scorecard where the chosen option wins on every single criterion — a sign of reverse-engineered weights.
- Using a generic, reusable criteria checklist instead of deriving criteria from this decision's actual constraints.
- Calling a decision "reversible" based on API-surface compatibility alone, without checking data/state or organizational lock-in.
- Defending a past decision as flawless under pushback instead of conceding genuine weaknesses.
- Treating build-vs-buy as a permanent verdict rather than one worth revisiting as the vendor market matures.
- No documented "what would change this decision" — meaning the same debate re-litigates from scratch every time someone new asks.
- Applying "build vs buy" as a single binary to an entire AI system instead of asking which layers to own versus delegate.

---

## Cheat card

```
CLASSIFY FIRST          reversible (2-way door): decide fast, lowest competent level, no ADR
                         one-way door: decide slow, more input, ADR required
  check THREE things, not just API compatibility:
    1. data/state lock-in (schemas, fine-tuned artifacts, eval harnesses)
    2. organizational lock-in (retraining, new on-call shape, new pipeline)
    3. blast radius (how many systems/teams depend on this being stable)

SCORECARD                weighted_total = Σ(weight × score), criteria DERIVED from
                          THIS decision's constraints, not a generic checklist
  red flag: winner wins EVERY criterion → weights were reverse-engineered
  good scorecard: winner loses 1-2 criteria explicitly, wins on what you said mattered

BUILD vs BUY vs ASSEMBLE  buy: undifferentiated plumbing (auth, payments, email)
                           build: touches revenue/retention/margin/moat
                           assemble/OSS: commoditized building block, you run it
  test: "does this touch differentiation?" not "can we build it?"

AI-SPECIFIC LOCK-IN      model/vendor swap LOOKS reversible (API compatible) but
                         fine-tuning data + prompts + eval harness rarely transfer —
                         treat as closer to one-way door unless deliberately
                         kept provider-agnostic from day one

ADR TEMPLATE             Title · Status · Context (forces incl. non-technical) ·
                         Decision · Consequences · Alternatives considered (w/ why rejected) ·
                         What would change this decision (concrete trigger)
  scope: architecturally significant / hard to reverse / precedent-setting ONLY
  never edit after acceptance — supersede, keep history intact

DEFENDING UNDER PRESSURE  1) restate the CONSTRAINT that drove it, not the decision
                          2) name what would change your mind, concretely
                          3) concede the real tradeoff explicitly, hold the conclusion
```

## Sources

- [Build vs Buy vs Partner Framework 2026 — thecodev.co.uk](https://thecodev.co.uk/build-vs-buy-framework/) — accessed 2026-08-02
- [Build vs Buy AI in 2026: The Definitive Enterprise Framework — inteligenai.com](https://inteligenai.com/how-to-navigate-the-build-vs-buy-ai-in-2026/) — accessed 2026-08-02
- [How Great Engineers Make Architectural Decisions — ADRs, Trade-offs, and an ATAM-Lite Checklist — Microsoft Community Hub](https://techcommunity.microsoft.com/blog/azurearchitectureblog/how-great-engineers-make-architectural-decisions-%E2%80%94-adrs-trade-offs-and-an-atam-l/4463013) — accessed 2026-08-02
- [Architectural Decision Records (ADRs) — adr.github.io](https://adr.github.io/) — accessed 2026-08-02
- [Architecture Decision Records: A Practical Guide for 2026 — John Pratt](https://www.john-pratt.com/architecture-decision-record) — accessed 2026-08-02

## Changelog
- 2026-08-02 — created
