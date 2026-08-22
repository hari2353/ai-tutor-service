# Principal-Level Code Review, Giving and Receiving

> **Track:** T13 SDE Craft & Vibe Coding · **Time:** 2h · **Prereqs:** `T27-pr-review` · **Updated:** 2026-08-03
> **Module id:** `T13-code-review` · **Tags:** review, leadership, critical

## The 30-second version

Below staff level, code review is a correctness-and-security gate; at principal level it's a leadership instrument, and the two failure modes that separate a principal reviewer from a competent senior one are architectural blast radius (does this change quietly widen the blast radius of a future incident, by coupling two things that should stay independent, three PRs before anyone notices) and "is this the right problem" (a technically excellent PR that solves a problem the team shouldn't be spending its scarce attention on right now). Giving review feedback that actually changes behavior means naming the specific future cost, not the preference — "this will need to change in two places next time" lands, "I'd have done it differently" gets argued with, correctly. Receiving review well at the principal level means treating a blocking comment on a design you own as data, not an attack, and distinguishing a real objection (a stated cost) from a taste preference dressed as one — the tell is whether the reviewer can name what specifically breaks and when. The signal an interviewer is actually probing for is whether review is something you do *to* people or *with* them: a principal engineer's review comments are training data for the whole team's future decisions, for better or worse, and that's a different job than catching bugs.

## Why this gets asked

Because by the principal level, an engineer's individual code output stops being the leverage point — the leverage point is the judgment they encode into every review they do, and whether junior and mid-level engineers on the team get measurably better at making decisions because of the comments this person leaves, or measurably more defensive and conflict-averse because review with them is unpleasant. The interviewer has almost certainly worked under (or watched a report suffer under) a "principal" reviewer who was technically right and organizationally toxic — nitpicking style on a junior's first PR while missing an actual security hole three files over, or blocking every PR on a personal architectural preference until people stopped sending them anything they hadn't already privately validated would pass. They want evidence the candidate has actually internalized that review is a coaching relationship with a technical gate attached, not the other way around.

---

## Lineage: past → present → future

**What came before.** Individual-contributor-era code review (pre-~2015 at most companies, and still the norm at many today) treated review purely as a correctness/security/style gate performed by whoever happened to be assigned — the mechanics of that gate, review order, triage strategy for large diffs, are covered thoroughly in `T27-pr-review`. The specific pain this narrow framing produces at scale: a team where every senior engineer reviews the same way regardless of who authored the PR gets technically-correct software and a flat, non-improving distribution of skill across the team, because nobody is using review as a teaching moment — junior engineers make the same category of mistake in PR 50 that they made in PR 5, because feedback was corrective ("fix this") rather than developmental ("here's the pattern this represents, and here's why it matters three services from now").

**Where it stands now.** The consensus among engineering-leadership writing (Will Larson's *Staff Engineer*, Camille Fournier's *The Manager's Path*, and the informal but widely-cited "review as multiplier" framing that circulates in staff/principal-level engineering blogs) is that senior-plus review has two jobs simultaneously: gatekeeping (does this ship safely) and multiplication (does the team that produced this get better at producing the next one without this reviewer in the loop). The live disagreement is how much architectural pushback a principal reviewer should exercise on a PR that's correct, tested, and shipped by someone who owns the area — some organizations explicitly protect team autonomy and expect a principal to raise concerns as a conversation rather than a block outside their own team's code; others expect principal-level review authority to cross team boundaries freely because architectural coupling doesn't respect org charts. What's genuinely, universally agreed: blocking a correct, tested, low-risk PR on pure taste with no stated future cost is the single most common way review authority gets resented and routed around.

**Where it's heading.** As AI-assisted code generation absorbs more of the mechanical review layer (import/API-existence checks, style, basic null-safety patterns — covered in `T27-reviewing-ai-code`), the human review budget at every level, not just principal, is shifting toward exactly the two things this module covers: architectural fit and "is this the right problem," because those are the two categories current AI review tooling still can't reliably judge, since both require holding context (team roadmap, on-call history, org priorities) no repo-local tool has access to. This is a confident, already-observable trend, not speculation — it's the explicit reasoning `T27-reviewing-ai-code` gives for why AI review tools are trusted on import verification and pattern consistency but not yet on design-fit judgment.

---

## Mental model

```
WHERE REVIEW AUTHORITY OPERATES, BY LEVEL

  JUNIOR/MID REVIEWER          SENIOR REVIEWER              PRINCIPAL REVIEWER
  ─────────────────────        ─────────────────────        ─────────────────────
  "does this work?"            "does this work AND          "does this work, fit,
  "does this follow             fit the codebase's           AND is it the RIGHT
   the style guide?"            existing shape?"              problem to be solving
                                                                right now?"
                                                              "what does this
                                                               COUPLE to what,
                                                               three PRs from now?"

  gate: correctness+style      gate: + design fit           gate: + blast radius,
                                                               + problem selection
  ALL THREE ALSO: is this a teaching moment, and does my comment change behavior
  or just get complied with once and forgotten?

FEEDBACK THAT LANDS vs FEEDBACK THAT GETS ARGUED WITH

  "I'd have done this differently"        <- preference, gets litigated, correctly
  "this couples module A to module B;     <- stated COST, specific, hard to argue
   next quarter's migration now needs         with because it's a concrete claim,
   to touch both instead of one"              not a taste

  BLOCKING language reserved for: correctness, security, a NAMED future cost
  "consider" language for: everything else, including things you'd have done
   differently with no identifiable cost
```

## How it actually works

### Architectural blast radius — the review most juniors don't know to do

A correctness-focused review asks "does this function do what it claims." A blast-radius review asks "what does this change make possible, or impossible, for code that doesn't exist yet." Concretely: a PR that adds a direct database call from service A into service B's schema (bypassing B's API) is often locally correct and passes every test — the blast radius question is what happens when B's team migrates that table next quarter and doesn't know A depends on its internal shape, or when B adds a write path that now needs to invalidate a cache A doesn't know exists. This is the review most junior reviewers miss entirely, because nothing about the diff itself is wrong — the risk is entirely in what it enables or forecloses for code that hasn't been written yet, which requires holding a mental model of the whole system's dependency graph, not just the file in front of you. Size is the first-order confounder here: the widely-cited SmartBear/Cisco studies found review effectiveness falls off a cliff past roughly 200–400 changed lines — above ~400 LOC reviewers find mostly cosmetics while real defects slip through — so a boundary-crossing PR of 800+ lines is not reviewed, it is rubber-stamped with extra steps, and the correct review comment is "split this by ownership boundary," not an attempt to review it as one artifact. The concrete technique: for any PR touching a boundary between two owned areas, ask "if the *other* side changes in the most likely way it will change next, does this PR's assumption still hold" — and if the answer is "I'd have to check with them," that's the actual review comment, not a rubber stamp.

### Hidden coupling — the review that catches what tests can't

Hidden coupling is architecturally distinct from an interface violation: it's a dependency that exists in practice (shared assumptions about ordering, timing, an implicit contract about what fields are always populated) without existing in any type signature or API contract a linter could check. The tell in review: a PR that "just" changes an internal implementation detail — the order two fields get set in, whether a cache is populated before or after a write — and the reviewer's job is asking who else might be relying on the *old* order even though nothing declares that dependency anywhere. This is expensive to review well because it requires either deep tribal knowledge of the codebase's actual (not documented) behavior, or the discipline to grep for every caller and read what assumptions they make, not just whether they compile against the new signature. Principal-level reviewers catch this class of bug disproportionately because they've usually been paged for the production incident this exact pattern caused once already, somewhere.

### "Is this the right problem to solve" — the review most reviewers are never taught to do

This is the review that has nothing to do with the code's quality and everything to do with organizational judgment: a PR can be excellently written, fully tested, architecturally sound, and still be the wrong thing to ship this sprint because it solves a problem that isn't actually the team's highest-leverage problem right now, or solves a real problem in a way that commits the team to a direction that conflicts with a roadmap decision the author wasn't in the room for. This review is uncomfortable to give because it isn't about the code at all — it's a scope/priority conversation dressed as a review comment — and it's exactly the review most reviewers, even senior ones, never learned to do, because it requires context (the roadmap, a recent leadership decision, a tradeoff made in a meeting the author missed) that isn't visible in the diff and has to be supplied by the reviewer. The failure mode when this review is skipped: a team ships a technically excellent feature nobody asked for, or re-solves a problem a parallel effort already addressed, discovered only when the two efforts collide in production or in a later planning meeting.

### Giving feedback that changes behavior, not just gets complied with

The mechanical difference between feedback that sticks and feedback that gets grudgingly applied once and forgotten: naming the specific mechanism of future cost ("this will need a matching change in the retry handler next time someone touches timeout behavior, because the two are now implicitly coupled through this shared constant") versus asserting a preference ("I'd structure this differently"). The first gives the author (and anyone reading the review later) a transferable piece of judgment they can apply to their *next* PR without this reviewer present; the second only produces compliance on *this* PR, if that, and often produces quiet resentment because a preference framed as a requirement is, correctly, arguable. The empirical backing for prioritizing this: Mäntylä & Lassenius's classification of ~6,000 real review comments found roughly 75% concern evolvability (understandability, documentation, naming) rather than functional defects — so most review value is teaching-transfer by default, whether the reviewer intends it or not. And Bacchelli & Bird's Microsoft study found only about 20–25% of comments lead to a code change; comments that name no concrete cost land in the majority that changes nothing. A useful self-check before posting a review comment: could I state, in one sentence, what specifically breaks and under what future condition — if not, the comment is a preference and should be phrased as "consider," not "please change."

### Receiving review well at senior/principal level

The failure mode at this level isn't usually defensiveness in the crude sense (arguing loudly) — it's a subtler one: treating every comment on a design you own as requiring a defense, rather than triaging first whether the comment identifies a real, stated cost or is a preference you're free to accept or decline. The actual skill is the triage, done quickly and out loud: "is there a concrete cost named here, and is it one that compounds (gets more expensive over time) or is one-time" — a compounding cost is worth addressing even under deadline pressure, because the two-day fix now is cheaper than paying the cost repeatedly; a one-time cost is a legitimate tradeoff to accept and ship. Distinguishing a real objection from a style preference is genuinely hard to do about your own work in the moment, which is exactly why "does this comment name a specific, concrete cost" is a mechanical test worth applying deliberately rather than trusting your in-the-moment emotional read of whether a comment feels fair. Latency is part of receiving well, too: Google's published norm is response within one business day, and McIntosh et al.'s study work ties both review latency and participation to fewer post-release defects — a review that lands 3 days late has most of its value decayed, because the author has context-loaded onto the next task; treating "same or next business day" as an SLO on your own reviews is the single highest-leverage habit change for most senior engineers.

## Build it from scratch

A minimal exercise for practicing blast-radius review, runnable against any PR touching a service boundary:

```bash
# untested sketch — blast-radius triage questions for any PR crossing an owned boundary
# 1. What does this PR assume about the OTHER side that isn't checked by a type or test?
grep -rn "TODO\|assumes\|expects" <diff files>   # explicit admissions are a start,
                                                    # but the real ones are unstated

# 2. If the other side's owning team changed the most LIKELY next thing about their
#    system, does this PR's behavior still hold? Write the answer down, don't just think it.
#    e.g.: "If InventoryService adds a second warehouse per SKU, does this PR's
#    assumption of one warehouse per SKU silently produce wrong results, or fail loudly?"

# 3. Grep every OTHER caller of anything this PR changes the behavior of,
#    not just whether they compile against a new signature
git grep -n "shared_cache_key\|write_order_flag" -- '*.py' | grep -v "$(git diff --name-only)"

# 4. Ask the "right problem" question explicitly, out loud, before approving:
#    does this PR's existence align with what the team is actually supposed to
#    be prioritizing this cycle -- and if you don't know, that's the comment.
```

This isn't a tool, it's a checklist that forces the two principal-level reviews (blast radius, hidden coupling) to happen deliberately rather than being skipped in favor of the faster correctness/style pass that `T27-pr-review` already covers well.

## How it's done in production

| Symptom | Cause | Fix |
|---|---|---|
| A "clean" PR breaks a neighboring service three weeks later when that team makes an unrelated change | Hidden coupling or an unstated cross-boundary assumption never surfaced in review | Ask explicitly, for every boundary-crossing PR: "if the other side changes in its most likely next way, does this still hold" — and grep actual callers, not just type signatures |
| A principal engineer's reviews are technically correct but engineers dread being reviewed by them | Feedback phrased as preference/rewrite rather than a named future cost; correction with no teaching | Reserve blocking language for correctness, security, and a stated compounding cost; everything else as "consider," explicitly modeling the distinction so it's learnable |
| A technically excellent feature ships and nobody asked for it, or it duplicates a parallel effort | No "is this the right problem" review — reviewers checked code quality, not organizational fit | Make "does this align with current priorities, and did the author have the context to know that" an explicit, named review step, not an assumed background check |
| Junior engineers make the same category of mistake in PR 50 as PR 5 | Review feedback has been corrective ("fix this line") without ever naming the transferable pattern behind it | Rewrite recurring corrections as a named pattern with a stated cost, ideally documented once (a wiki note, a lint rule) rather than re-explained per PR |
| A senior/principal engineer argues with every blocking comment on their own PRs | No triage step before responding — treating every comment as requiring defense rather than classification | Apply the concrete-cost test to every comment received: does it name what breaks and when; accept compounding-cost comments even under deadline pressure, argue preference-only ones on their merits |
| Review authority is respected within a team but resented across team boundaries | Principal reviewer exercises architectural pushback on another team's code without the local context that team has | Frame cross-team architectural concerns as a question ("what happens when X changes on your side") rather than a directive, since the local team usually has context the reviewer doesn't |
| A design is blocked repeatedly on stylistic preference with no compounding cost identified | Reviewer conflating "not how I'd have built it" with "this is wrong" | Apply the same concrete-cost test to your own comments before posting them: if you can't name what breaks and when, it's a suggestion, not a block |

## Tradeoffs & when NOT to use it

- **Don't apply principal-level architectural scrutiny to every PR regardless of blast radius.** A config value bump or a well-tested internal refactor with no cross-boundary effect doesn't need a blast-radius review — calibrate depth to what the change actually touches, not to a fixed process applied uniformly.
- **Don't exercise cross-team architectural authority as a directive rather than a question.** The local team almost always has context (recent decisions, constraints, a roadmap item) the reviewer doesn't; framing a genuine concern as "what happens when X changes" invites the missing context out, framing it as "you should do Y" invites defensiveness and often turns out to be wrong once the missing context surfaces.
- **Don't treat "is this the right problem" as a review you're entitled to raise on every PR.** It's appropriate when you have the organizational context to actually know the answer — raising it as a vague gut feeling without being able to name what it conflicts with is itself an unhelpful, unaccountable review comment, no better than an unstated architectural preference.
- **Don't confuse teaching-oriented feedback with therapy.** The goal of naming a transferable pattern is that the *next* PR needs less correction, not that every review becomes a lengthy mentorship essay — the same discipline that makes a comment land (name the specific cost) also keeps it short.
- **Don't accept every blocking comment on your own work just because you're being a good sport about feedback.** Triage first; a preference dressed as a block deserves pushback on the merits, and reflexive compliance from senior engineers under review pressure is exactly how weak architectural opinions calcify into unquestioned team conventions.

---

## Interview questions

### Q1 — What does "architectural blast radius" mean in a code review, and give a concrete example of a PR that passes every test but has a large one?
**Testing:** whether the candidate can name the review category, not just recognize it when described.
**Answer:** Blast radius is what a change makes possible or impossible for code that doesn't exist yet — not whether the diff itself is correct. Example: service A adding a direct read from service B's database table, bypassing B's API. It's locally correct and passes tests today; the blast radius is that B's team can no longer freely change that table's schema or add a write path without knowing A silently depends on its current shape, discovered only when B's migration breaks A in production.
**Follow-up trap:** *"How would a reviewer actually catch this without knowing every other team's future plans?"* — by asking the question explicitly rather than psychically predicting the future: "if the owning team changes this in the most likely next way, does this PR's assumption still hold" — and if the answer requires checking with them, that's the review comment itself, not a blocker requiring omniscience.

### Q2 — What's the difference between a hidden-coupling bug and an interface violation, and why is hidden coupling harder to catch in review?
**Testing:** precise distinction, not a vague "coupling is bad."
**Answer:** An interface violation is checkable mechanically — a linter or type checker can flag it. Hidden coupling is a dependency that exists in practice (an implicit ordering assumption, a field always populated in one code path that another caller silently relies on) without existing in any type signature, contract, or test a tool would check. It's harder to catch because catching it requires either deep tribal knowledge of actual runtime behavior or manually grepping every caller and reading their assumptions, not just confirming they compile.
**Follow-up trap:** *"If nothing declares the dependency anywhere, how would you even know to look for it?"* — pattern recognition from having been paged for exactly this class of incident before is the honest answer; mechanically, treat any change to ordering, timing, or "when a field gets populated" as suspicious by default and grep every caller regardless of whether the type signature changed.

### Q3 — Give feedback on a PR where you fundamentally disagree with the approach, but it's correct and tested. How do you phrase it so it changes future behavior rather than just getting argued with?
**Testing:** the central "feedback that lands" skill.
**Answer:** Distinguish a stated future cost from a preference before writing anything. If there's a concrete, nameable cost (duplicated logic that will drift, a pattern the team explicitly moved away from for a documented reason, an abstraction violation that makes another module untestable in isolation), state it specifically and as blocking. If it's genuinely "I'd have structured this differently" with no identifiable cost, phrase it as "consider" and approve — repeatedly blocking correct, tested code on unstated preference is what makes review authority get routed around.
**Follow-up trap:** *"The author says your suggested approach costs two extra days and this ships today. Do you hold the block?"* — re-evaluate against whether the cost you named compounds or is one-time: a compounding cost (every future feature in this area now has to work around the wrong abstraction) is cheaper to pay once, even at two days, than repeatedly; a one-time cost is a legitimate tradeoff to ship now and accept.

### Q4 — You're the most senior reviewer on a PR from a junior engineer. What's different about how you review it compared to a peer's PR, and what stays the same?
**Testing:** whether review is understood as a teaching act at senior level, without a double standard on correctness.
**Answer:** Correctness, security, and blast-radius scrutiny stay identical — a junior's bug is exactly as dangerous in production as a senior's. What changes is the shape of the feedback: naming the transferable pattern behind a correction explicitly, rather than just fixing the line, so the same category of mistake doesn't recur in PR 50. It's slower per-review and pays off across many future PRs, which is exactly the multiplier framing that separates senior-plus review from junior review.
**Follow-up trap:** *"Isn't that condescending — treating a junior's PR as a teaching opportunity by default?"* — the tell is whether the comment assumes ignorance versus names a pattern for anyone's benefit; "here's the pattern this represents and why it matters three services from now" is useful regardless of the author's seniority, and phrasing it that way rather than as remedial instruction avoids the condescension while keeping the teaching value.

### Q5 — A staff engineer on another team blocks your PR on an architectural concern you believe reflects a misunderstanding of your system's actual constraints. How do you handle it?
**Testing:** receiving cross-team review well without either capitulating or stonewalling.
**Answer:** Ask them to state the specific cost they're worried about, concretely and with a scenario — this either surfaces a real gap in your design you hadn't considered, or surfaces that they're missing local context you have. Supply the missing context directly and specifically ("here's why that scenario can't actually occur, because of X constraint") rather than asserting seniority or defensiveness. If the concern is real once the context is exchanged, address it; if it dissolves once context is supplied, that's a legitimate resolution, not a loss for either side.
**Follow-up trap:** *"What if they still insist after you've supplied the context?"* — escalate to whoever owns the actual disagreement (an architecture review forum, a shared manager, or simply asking a third senior engineer with context on both systems to weigh in) rather than either overriding them unilaterally or blocking your own shipped work indefinitely on an unresolved disagreement — the failure mode to avoid is silent standoff.

### Q6 — What makes the "is this the right problem to solve" review different from every other review category, and why do most reviewers, even senior ones, skip it?
**Testing:** understanding the organizational-context requirement of this review.
**Answer:** It has nothing to do with the code's quality — a PR can be excellent, tested, and architecturally sound and still be the wrong thing to ship this cycle. Most reviewers skip it because it requires context that isn't in the diff at all: the current roadmap, a recent leadership tradeoff decision, or knowledge that a parallel effort already addresses this. Reviewing code quality is something any competent engineer can do from the diff alone; this review requires organizational awareness the diff can't supply.
**Follow-up trap:** *"Isn't raising this risk being seen as overstepping, especially on someone else's team?"* — frame it as a question, not a verdict: "does this align with what's currently prioritized — has this been checked against the roadmap?" rather than "this shouldn't be built." If you genuinely don't have the context to answer confidently, the honest move is naming the uncertainty rather than either staying silent or asserting an opinion you can't back.

### Q7 — How do you tell the difference, receiving review, between a real objection and a style preference dressed as a requirement?
**Testing:** the concrete triage mechanism for receiving feedback well.
**Answer:** Ask whether the comment names a specific, concrete cost and a condition under which it manifests — "this will need a matching change in two places next time X happens" is a real objection; "I'd have used a different pattern here" with no stated consequence is a preference. The mechanical test protects against the emotional read in the moment, which tends to either over- or under-weight a comment based on who delivered it or how it's phrased rather than what it actually claims.
**Follow-up trap:** *"What if the reviewer is more senior and you're not sure you're allowed to push back with this triage?"* — seniority doesn't exempt a comment from the same test; a senior reviewer's unstated preference is still a preference, and the professional move is asking them directly to name the cost ("can you help me understand what specifically breaks here?") rather than either deferring reflexively or dismissing it — that question alone often resolves the ambiguity for both people.

### Q8 — A principal engineer's review comments are technically always correct, but engineers on the team dread being reviewed by them and increasingly avoid sending them anything risky. Diagnose the organizational failure.
**Testing:** recognizing review-as-leadership-signal failing even when the technical content is right.
**Answer:** Being correct isn't sufficient — the delivery is training data for how the team behaves going forward, and if every interaction is corrective without being developmental (naming the transferable pattern, distinguishing blocking-worthy costs from preferences), engineers learn to route around the reviewer rather than internalize the judgment. The measurable failure: engineers pre-filtering what they send this person, which means the reviewer is no longer actually seeing the team's real, current risk — exactly the opposite of what review authority is for.
**Follow-up trap:** *"How would you actually detect this is happening, versus just being technically demanding?"* — look for behavioral evidence, not self-report: are PRs to this reviewer getting smaller and more conservative over time relative to the same authors' PRs to other reviewers, are risky architectural decisions getting made and shipped without going through this reviewer at all, and is this reviewer's queue conspicuously empty of exactly the changes that most need principal-level scrutiny.

### Q9 — What's a compounding cost versus a one-time cost in a design disagreement, and why does the distinction matter under deadline pressure?
**Testing:** the actual decision procedure for whether to hold a block under time pressure.
**Answer:** A one-time cost is paid once and doesn't recur — a slightly awkward one-off migration, a bit of extra cleanup later. A compounding cost recurs and grows — every future feature built in this area now has to work around a wrong abstraction, or every future incident in this path is harder to debug because of a coupling introduced now. Under deadline pressure, a one-time cost is often legitimately worth accepting to ship; a compounding cost is usually cheaper to pay immediately, even at real short-term cost, because the alternative is paying it repeatedly at growing scale.
**Follow-up trap:** *"How do you actually estimate whether a cost compounds, rather than just asserting it does?"* — name the next concrete instance where it would recur (the next feature that will touch this area, the next incident type this coupling would complicate) — if you can't name a plausible next occurrence, you likely don't actually have evidence it compounds, and the honest move is downgrading your own claim to a one-time cost or a preference.

### Q10 — Staff/principal-level: your org is scaling AI-assisted code generation heavily, and the mechanical layer of review (import verification, style, obvious null-safety patterns) is increasingly automated. What does that do to what a principal-level human reviewer should actually spend their time on?
**Testing:** connecting this module to the current shift in where human review adds value.
**Answer:** It concentrates the human review budget onto exactly the two categories this module is about — architectural blast radius and "is this the right problem" — because both require holding organizational context (the roadmap, the dependency graph's likely future changes, prior incidents) that no repo-local AI review tool has access to, unlike import existence or style consistency, which are increasingly reliably automatable. The principal-level job doesn't shrink as the mechanical layer gets automated; it gets more concentrated and more valuable, because it's the residual category automation structurally can't reach.
**Follow-up trap:** *"Could an AI reviewer eventually do blast-radius or problem-selection review too, given enough repo context?"* — treat this skeptically for now: both require reasoning about intent and organizational priorities, not just repo-local patterns, and current tooling (per `T27-reviewing-ai-code`) is meaningfully more reliable on pattern-consistency checks than on design-fit judgment — a confident claim that this is "solved" in 2026 is itself a red flag to push back on in an interview, not a fact to accept.

---

## Red flags that fail you

- Describing code review purely as a correctness/style gate with no mention of blast radius, hidden coupling, or problem-selection review.
- Giving feedback phrased as personal preference ("I'd have done it differently") without a stated, concrete future cost.
- Blocking a correct, tested, low-risk PR on architectural taste with no named cost.
- Treating every blocking comment received as requiring defense, with no triage for whether it names a real cost.
- Exercising cross-team architectural authority as a directive rather than a question, especially without acknowledging the local team likely has context you don't.
- Raising "is this the right problem" as an unaccountable gut feeling rather than tied to actual roadmap/priority knowledge.
- Not recognizing that review feedback style is itself a leadership signal that shapes whether engineers route around a reviewer.

## Cheat card

```
THREE REVIEW LAYERS BY LEVEL (each layer ADDS to the ones below it):
  junior/mid:  correctness + style + security (mechanics: T27-pr-review)
  senior:      + does this fit the codebase's existing shape (design)
  principal:   + BLAST RADIUS (what does this couple/foreclose later)
               + HIDDEN COUPLING (implicit assumption, no type checks it)
               + IS THIS THE RIGHT PROBLEM (needs roadmap/org context)

BLAST RADIUS: ask "if the OTHER side changes in its most likely next
  way, does this PR's assumption still hold?" -- if you'd have to check
  with them, THAT is the review comment.

HIDDEN COUPLING: an implicit dependency (ordering, timing, "field X is
  always populated here") with NOTHING in a type/contract/test checking
  it. Grep every caller's ASSUMPTIONS, not just whether they compile.

FEEDBACK THAT LANDS: names a specific, concrete, TRANSFERABLE cost
  ("this will need a matching change in Y next time Z happens").
FEEDBACK THAT GETS ARGUED WITH (correctly): "I'd have done it
  differently" with no stated cost -- that's a preference, phrase as
  "consider," not a block.

RECEIVING REVIEW: triage every comment -- does it name a specific cost
  and WHEN it manifests? Compounding cost (recurs, grows) -> address
  even under deadline pressure. One-time cost -> legitimate to accept
  and ship. No stated cost -> it's a preference, push back on merits.

CROSS-TEAM REVIEW: frame architectural concerns as a QUESTION ("what
  happens when X changes on your side"), not a directive -- the local
  team usually has context you don't.

"RIGHT PROBLEM" REVIEW: has nothing to do with code quality. Requires
  roadmap/priority context. Raise as a question if uncertain, not a verdict.

2026 SHIFT: AI review absorbs the mechanical layer (imports, style,
  null-safety patterns -- see T27-reviewing-ai-code). Human principal
  review concentrates on blast radius + problem selection, the two
  categories requiring organizational context automation can't reach.
```

## Sources

- [Staff Engineer: Leadership Beyond the Management Track — Will Larson](https://staffeng.com/) — accessed 2026-08-03
- [The Manager's Path — Camille Fournier, O'Reilly] — accessed 2026-08-03
- `T27-pr-review` — review order, triage strategy for large diffs, security-focused mechanics (this repo)
- `T27-reviewing-ai-code` — the ten LLM-specific failure modes and why AI review tooling is trusted on mechanical checks but not design-fit judgment (this repo)

## Changelog
- 2026-08-03 — created
