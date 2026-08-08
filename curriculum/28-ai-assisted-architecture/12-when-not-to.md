# When NOT to Let an Agent Write It: The Failure Taxonomy

> **Track:** T28 AI-Assisted Architecture (Claude) · **Time:** 1.5h · **Prereqs:** none · **Updated:** 2026-08-01
> **Module id:** `T28-when-not-to` · **Tags:** judgment, critical

## The 30-second version

Eight categories of code reliably break agentic generation, each with its own observable failure symptom rather than a vague "it might be wrong": novel algorithms with no training precedent (confidently produces a known-but-wrong algorithm instead of the actual novel one), anything needing a correctness proof (a valid-looking proof from an unfaithful formalization of the problem), security-critical code — crypto, authz, session handling — (measured at 86% pass rate on cryptographic implementations specifically, meaning roughly one in seven ships an exploitable weakness, with authorization misconfiguration the single most common backend failure), code whose requirements live in someone's head (the model fills the gap with a plausible default instead of asking, and plausible is not correct), performance-critical inner loops (pattern-matches "clean-looking" code that reintroduces allocation-in-a-loop or nested iteration a profiler would catch and a diff review won't), large refactors without test coverage (a confident, silent behavior change with nothing to signal it happened), domains you cannot personally review (comprehension debt: code you can read but not evaluate), and regulated code needing provenance (no auditable chain from requirement to implementation, which fails a compliance review regardless of whether the code works). The real decision rule underneath all eight is the review-cost inversion: delegate only when reviewing the output costs less than writing it yourself, and for every category on this list that inequality flips, because verifying a claim in an unfamiliar or high-stakes domain is reliably more expensive than authoring it firsthand. The single most dangerous failure is not the code being wrong, it's automation bias: 96% of developers report not fully trusting AI-generated code, and only 48% consistently verify it before merging anyway — that thirty-point gap between stated distrust and actual behavior is where the real incidents come from, not from generation quality itself.

## Why this gets asked

Because by 2026 every candidate has a story about AI writing good code, and almost none have a story about the specific thing they refused to let it write and why — which is the harder, more valuable answer. The interviewer has shipped an incident from exactly one of these eight categories: a plausible-looking cryptographic implementation that was subtly wrong, a refactor that silently broke a behavior no test covered, a security review that took longer than the feature took to build because nobody could tell what the generated authorization logic actually enforced. They are testing whether you have a real taxonomy with real symptoms, or a vague unease you'd abandon under deadline pressure — and this module is explicitly the most opinionated one in the track because the interviewer wants a stance, not a survey.

---

## Lineage: past → present → future

**What came before.** The 2023-2024 default was universal caution: review every line, trust nothing, because early models hallucinated APIs constantly and the failure mode was obvious — code that didn't compile, functions that didn't exist. That caution was cheap to apply because generation itself was narrow (autocomplete, single functions) and slow enough that review kept pace. The pain that killed universal caution as a strategy was economic: as generation got dramatically faster and scope grew from functions to entire features, blanket "review everything with equal suspicion" stopped being affordable, and teams that kept doing it anyway simply became review-bottlenecked, which is exactly the failure DORA's 2025-2026 data documents at scale (`T28-claude-architect`: 98% more PRs merged, review time up 91%, and the 2026 follow-up showing median review time up 441% with 31% more PRs merging with zero review at all). The pain that killed *uniform* trust, the opposite failure, is this module's subject: teams that responded to the review bottleneck by trusting the plausible cases too, and got burned specifically in the categories where plausibility and correctness come apart hardest.

**Where it stands now.** The empirical picture is a genuine split rather than a single trend line, and stating it honestly matters more here than in most modules. Security pass rates for AI-generated code have stalled, not improved, at roughly 56% overall — almost exactly where they started — meaning a generated snippet introduces an OWASP Top 10-class vulnerability nearly 44% of the time across categories ([Veracode 2026 GenAI Code Security, accessed 2026-08-01](https://thenextweb.com/news/veracode-2026-genai-code-security-56-percent-pass-rate)), with real variance by category: cryptographic implementations specifically pass at 86% (meaning roughly 1 in 7 still ships an insecure crypto choice), and by language, with Java the worst-measured at a 29% pass rate. Meanwhile the generation-versus-review asymmetry has become the dominant lived experience of teams running this at scale: generation cost dropped roughly two orders of magnitude in three years, while human comprehension of unfamiliar code did not speed up at all across the same period ([Code Is Cheap. Review Is Expensive, accessed 2026-08-01](https://blog.kilo.ai/p/code-is-cheap-review-is-expensive)) — a four-minute generated feature can require an hour of careful review, and running two agents in parallel doubles the review queue, not the delivered throughput. The live disagreement is over automation bias specifically: one camp holds that better tooling (linters, hallucination detectors checking imports against the real dependency graph) will shrink the failure categories where confidence and correctness diverge; the harder-nosed camp, backed by the 96%-distrust-but-48%-verify gap, argues the problem was never model capability, it's that humans reliably under-act on stated distrust when correcting an AI's output costs extra effort — a documented property of automation bias generally, not specific to code.

**Where it's heading.** High confidence: the review bottleneck gets named and staffed as its own discipline rather than treated as an afterthought — Anthropic's own framing (`T28-claude-architect`) that verification, review, and security are now *the* constraint, not code-writing, is becoming the standard framing industry-wide, and expect review capacity, not generation capacity, to be the metric teams actually manage against. Medium confidence: static, pre-generation verification (import/API existence checks, the fixes already shrinking the fabricated-API failure mode per `T27-reviewing-ai-code`) narrows some categories on this list — likely security and correctness-adjacent ones where the failure has a checkable syntactic signature — while the categories that require judgment about intent (novel algorithms, tacit requirements, unfamiliar domains) are not obviously addressable by any tooling improvement on the horizon, because the missing information isn't in the code, it's in a human's head or in a problem nobody has solved before. Speculative: whether the review-cost inversion itself narrows as review tooling improves, or whether it widens, because generation capability keeps compounding faster than any review-assistance tooling has so far.

---

## Mental model

```
   THE REVIEW-COST INVERSION: the one question that generates the whole taxonomy

              cost to REVIEW the output          cost to WRITE it yourself
                        vs
   ┌──────────────────────────────────────────────────────────────────────┐
   │  REVIEW < WRITE  → delegate. this is the ordinary, good case.         │
   │  REVIEW > WRITE  → DON'T delegate. reviewing IS the expensive part,   │
   │                    and you pay it whether or not you also paid       │
   │                    for generation.                                    │
   └──────────────────────────────────────────────────────────────────────┘

   WHY REVIEW COST SPIKES IN EACH CATEGORY (the taxonomy is just this list):

   novel algorithm        → nothing to check output AGAINST (no known-correct answer)
   correctness proof      → verifying the proof is AS HARD as deriving it yourself
   security-critical      → a plausible-looking flaw needs security expertise to catch,
                              which is scarcer and slower than writing the code was
   tacit requirements     → you can't verify against a spec that only exists in someone's head
   perf-critical inner loop → correctness review passes; PERFORMANCE review needs a profiler,
                              a different skill, run at a different time
   large refactor, no tests → nothing MECHANICAL flags a silent behavior change
   unfamiliar domain       → you can read the code, you cannot evaluate whether it's right
                              (comprehension without judgment = comprehension debt)
   regulated / needs provenance → correct isn't sufficient; the REVIEW ITSELF must produce
                              an audit trail nothing about generation gives you for free
```

The one-sentence version: **every category on this list is a category where the thing that makes review expensive isn't the code's length, it's that nothing cheap exists to check the output against — and that absence is exactly what "delegate" assumes away.**

---

## How it actually works

### The eight failure categories, each with its observable symptom

**1. Novel algorithms with no training precedent.** *Symptom:* the model produces fluent, confidently-explained code that solves a *similar-looking, known* problem rather than the actual novel one — because generation is fundamentally pattern completion against training distribution, and a genuinely novel algorithm has no distribution to complete against. It will not say "I don't know how to do this"; it will produce something structurally correct-looking that quietly substitutes a known technique. **What to do instead:** design the algorithm yourself, using the model at most for boilerplate around a core you've derived, and treat any offered "here's how to solve X" for a problem you know is genuinely unprecedented as a signal to check what *known* problem it silently reduced yours to.

**2. Anything requiring a correctness proof.** *Symptom:* a valid-looking, well-structured proof built on an unfaithful formalization of the actual problem — the proof is internally consistent and the premises are wrong, which is far harder to catch than an invalid inference step, because reviewing it requires re-deriving the correct formalization from scratch, at which point you've done the proof yourself. Research on this specifically finds that formal systems guarantee proof *validity* but not that the formalization matched intent, and reviewer panels of models improve rigor without providing an absolute correctness guarantee ([arXiv 2604.19459, accessed 2026-08-01](https://arxiv.org/pdf/2604.19459)). **What to do instead:** use a model to explore proof strategies or catch obvious gaps, never as the sole author of a proof anything depends on; verify the formalization against the real problem statement independently before trusting any proof built on it.

**3. Security-critical code — crypto, authz, session handling.** *Symptom, with numbers:* cryptographic implementations pass security review at 86%, meaning roughly 1 in 7 ships an insecure choice (a weak mode, a reused nonce, an unvalidated parameter) that reads as ordinary crypto code to a non-specialist reviewer ([sqmagazine.co.uk AI Coding Security Vulnerability Statistics 2026, accessed 2026-08-01](https://sqmagazine.co.uk/ai-coding-security-vulnerability-statistics/)). Authorization is worse in a different way: misconfigured authentication and authorization flows are reported as the single most frequent class of failure in generated backend logic, and the failure is rarely a syntax error — it's a logic gap (a check that's present but scoped wrong, an early return that skips a later validation) that looks like correct code to anyone not specifically trained to spot the missing case. **What to do instead:** route this category through review by someone with explicit security training, every time, with no exception for "the diff looked small" — `T27-reviewing-ai-code`'s failure taxonomy for exactly this category applies directly here, and this module treats it as non-negotiable rather than a recommendation.

**4. Code whose requirements live in someone's head.** *Symptom:* the model fills an unstated requirement with a plausible default rather than surfacing the gap as a question, because "ask a clarifying question" is a weaker training signal than "produce a complete, confident answer" — the same next-token-confidence dynamic that produces hallucinated APIs produces hallucinated requirements. The generated code will look complete and will quietly encode an assumption ("delete probably means soft-delete," "the timeout is probably 30 seconds") that nobody actually decided. **What to do instead:** write the requirement down first, even briefly, before generating against it — if you can't write it down, that's diagnostic information that the requirement doesn't exist yet outside someone's head, and generating code against an unwritten requirement guarantees the code encodes whichever default the model reached for.

**5. Performance-critical inner loops.** *Symptom:* code that passes correctness review cleanly and silently reintroduces a known-bad pattern — string concatenation inside a loop, an allocation per iteration, an accidentally-quadratic nested loop — because these patterns are locally idiomatic and read as clean, idiomatic code to a reviewer checking correctness, not performance. Performance review requires a different tool (a profiler) run at a different time (under representative load) than a diff review catches, and few-shot prompting aimed specifically at performance can help but doesn't close the gap on its own ([PERFOPT-Bench, arXiv 2607.07744, accessed 2026-08-01](https://arxiv.org/pdf/2607.07744)). **What to do instead:** for code identified in advance as a hot path, benchmark before and after generation as a hard gate, not an afterthought — correctness review passing is not evidence about performance, and treating it as such is exactly how a regression ships invisibly.

**6. Large refactors without test coverage.** *Symptom:* a confident, plausible-looking refactor with no mechanism to signal that behavior silently changed, because nothing exists to check the *after* state against except a human reading two large diffs side by side and trying to hold the semantic equivalence in their head — which is exactly the comprehension-cost problem this whole module is about, applied to a diff instead of a single unfamiliar module. **What to do instead:** add characterization tests *before* the refactor, not after — a refactor without a pre-existing safety net is a rewrite wearing a smaller diff, and `T27-reviewing-ai-code`'s point about confidence carrying zero evidentiary weight applies with full force here: the refactor reads exactly as confidently whether it preserved behavior or not.

**7. Unfamiliar-to-you domains where you cannot review the output.** *Symptom:* comprehension debt — you can read the generated code, follow its control flow, and still have no way to judge whether it's *correct* for the domain, because correctness in an unfamiliar domain depends on facts about that domain you don't have, not on facts about the code's structure you can inspect. This is the general form Addy Osmani names specifically for AI-generated code, and it is dangerous precisely because it doesn't feel like ignorance — the code is readable, which creates false confidence that readable implies reviewable. **What to do instead:** either get a domain expert to review it, or treat the exercise as a forcing function to actually learn the domain before shipping anything built on it — "I don't understand this well enough to know if it's right" is a legitimate, senior thing to say, and shipping anyway is the actual failure, not the admission.

**8. Regulated code needing provenance.** *Symptom:* the code may be entirely correct and still fail a compliance review, because regulated contexts (financial calculations, medical logic, anything under SOC 2 / HIPAA / a specific industry's audit regime) require an auditable chain from requirement to implementation to test evidence, and generation on its own produces none of that chain by default — "an agent wrote this, it passed the tests" is not the same artifact as a documented decision trail a regulator or auditor can follow. **What to do instead:** build the provenance requirement into the workflow itself (the ADR discipline from `T28-ai-arch-review`, commit messages that reference the requirement, a human sign-off recorded as data, not just as a merged PR) rather than trying to reconstruct it after the fact, which is far more expensive than capturing it as you go.

### The review-cost inversion, stated as the actual decision rule

Every category above is a specific instance of one general inequality, and stating it as the rule rather than memorizing eight cases is the actual senior move: **delegate when reviewing the output costs less than producing it yourself; do not delegate when reviewing costs more.** The economy-wide version of this is now measured, not speculative — generation cost fell by roughly two orders of magnitude over three years while human comprehension speed of unfamiliar code did not improve at all across the same period, so the ratio between "cost to generate" and "cost to verify" has moved dramatically in one direction only. A four-minute agent-generated feature needing an hour of careful review is not a hypothetical; it is the reported shape of the asymmetry in production teams running this at scale.

The rule has a sharp corollary worth stating explicitly: **running more agents in parallel does not fix the inversion, it multiplies the queue on the expensive side.** Two agents each generating a feature in four minutes produces two hour-long review tasks, not one; throughput at the system level is bounded by review capacity, not generation capacity, the moment the inversion holds — which is why `T28-claude-architect`'s DORA figures (98% more PRs merged, review time up 91%, and by 2026, review time up 441% with 31% more PRs merging unreviewed) are the visible, organization-scale symptom of exactly this arithmetic, not a separate phenomenon.

### Automation bias: the failure underneath all eight categories

The taxonomy above describes where agent-generated code is *likely to be wrong*. It does not, by itself, explain why teams ship it anyway — that's a separate, human failure, and it's the more dangerous one because it operates independently of how good the tooling gets. The measured shape: 96% of developers report not fully trusting AI-generated code, and only 48% consistently verify it before merging — a roughly thirty-point gap between stated distrust and actual verification behavior ([Testing for Automation Bias, accessed 2026-08-01](https://medium.com/@kaylenstuart/testing-for-automation-bias-in-ai-systems-when-humans-trust-machines-a-little-too-much-d2c685289b5f)). This matches the general research finding on automation bias: people are measurably less likely to correct an erroneous suggestion when correcting it requires extra effort, or when they hold a favorable general attitude toward the tool producing it — which describes exactly the situation a reviewer is in when a diff looks clean and correcting a subtle, category-7-style domain error would mean going and learning the domain first.

**The named failure mode: plausible-but-wrong output exploiting the gap between stated caution and actual behavior.** The observable symptom is not "the code was wrong" — wrong code gets caught eventually. It's a pattern in incident postmortems: a reviewer who, when asked afterward, says they didn't fully trust the generated code, approved it anyway, because verifying it properly would have cost more effort than the review time they'd budgeted, and the code looked fine. This is why automation bias, not raw generation quality, is the harder problem in this module — a model that got measurably better at avoiding the eight failure categories above would still ship incidents through this gap, because the gap is in the human process, not the generation.

---

## Build it from scratch

Not code — the artifact worth building here is a pre-delegation checklist that operationalizes the review-cost inversion as a gate, not a vibe, before generation even starts:

```python
# untested sketch — a decision gate, not a scoring model; the point is
# forcing the question explicitly rather than defaulting to "delegate"
from enum import Enum

class Category(Enum):
    NOVEL_ALGORITHM = "no training precedent for the core technique"
    CORRECTNESS_PROOF = "a proof or formal guarantee is the deliverable"
    SECURITY_CRITICAL = "crypto, authz, session/credential handling"
    TACIT_REQUIREMENTS = "the spec exists only in someone's head, unwritten"
    PERF_CRITICAL_LOOP = "identified hot path, has a latency/throughput SLO"
    LARGE_REFACTOR_NO_TESTS = "behavior-preserving change, no characterization tests exist"
    UNFAMILIAR_DOMAIN = "I could not evaluate correctness of this myself"
    REGULATED_PROVENANCE = "needs an auditable requirement->implementation trail"

def should_delegate(task_categories: set[Category], est_write_hours: float,
                     est_review_hours: float) -> tuple[bool, str]:
    if task_categories:
        names = ", ".join(c.name for c in task_categories)
        return False, (
            f"Flagged categories present: {names}. Default to NOT delegating "
            f"until you've named what makes review cheap enough here despite "
            f"the category (e.g. a security-trained reviewer is already "
            f"assigned, or characterization tests exist for the refactor)."
        )
    if est_review_hours >= est_write_hours:
        return False, (
            f"Review cost (~{est_review_hours}h) >= write cost (~{est_write_hours}h). "
            f"The inversion holds even with no flagged category -- delegating "
            f"doesn't save time here, it just moves the cost to the review queue."
        )
    return True, "No flagged category, and review cost is genuinely lower than writing it."
```

The design point: category membership is a *hard* gate (returns `False` outright), not a score that averages against other factors, for the same reason `T28-harness-comparison`'s scoring rubric treats a disqualifying requirement as a gate rather than an average — a security-critical task that's otherwise trivial is still security-critical, and averaging that away is exactly the mistake this module exists to prevent.

---

## How it's done in production

| What production teams actually do | Why |
|---|---|
| **Mandatory human review with security training for category 3, no exceptions** | `T27-reviewing-ai-code`'s recommendation, treated here as non-negotiable rather than a suggestion — the 86%/29% pass-rate numbers mean "the diff looked fine" is not evidence of safety |
| **Characterization tests as a hard precondition for large refactors** | Converts category 6 from "hope the diff review catches drift" to a mechanical, automatable signal — the only category on this list where the fix is fully engineering, not judgment |
| **Pre-generation requirement capture (a one-paragraph spec, an ADR stub) for anything nontrivial** | Directly targets category 4 — if the requirement can't be written down before generating, that's the diagnostic, and it surfaces before code review rather than during it |
| **Performance budgets and profiler gates on identified hot paths** | Category 5's fix has to run at a different time than correctness review; production teams that skip this ship regressions that only show up under real load |
| **Provenance captured as workflow output, not reconstructed after the fact** | Category 8's audit trail (`T28-ai-arch-review`'s ADR discipline) is dramatically cheaper to capture as you go than to reconstruct once a regulator asks |
| **Explicit "I don't understand this well enough to review it" as an acceptable, expected review comment** | The only real countermeasure to category 7 and to automation bias generally — normalizing the admission is cheaper than the alternative, which is someone approving it anyway |

### What breaks at scale

| Symptom | Cause | Fix |
|---|---|---|
| Exploitable crypto or authz bug ships despite "the PR looked fine" | Security-critical code reviewed by someone without security training, or reviewed with the same scrutiny as ordinary code | Route category 3 to a security-trained reviewer unconditionally; treat "small diff" as irrelevant to the routing decision |
| A refactor silently changes behavior, discovered weeks later in production | No characterization tests existed before the refactor; nothing mechanical could have caught the drift | Characterization tests as a hard precondition, not a nice-to-have, before any refactor without existing coverage |
| A performance regression ships and is only caught under real load | Correctness review passed; nobody profiled the hot path because nothing flagged it as one | Maintain an explicit hot-path list with a benchmark gate in CI, independent of code review |
| A feature works but nobody can explain why a specific value was chosen, and a regulator asks | No provenance captured; the only record is a merged PR with a generated commit message | Capture requirement→decision→implementation as workflow output (ADRs, referenced tickets) at generation time |
| A reviewer says "I don't fully trust this" and approves it anyway | Automation bias — correcting requires extra effort, the diff looks plausible | Normalize blocking a PR on "I could not verify this" as a complete, sufficient review comment, not a personal failure to investigate further |
| Two agents run in parallel to "go faster," review queue backs up worse than before | Review-cost inversion; parallel generation multiplies the expensive side of the ratio, not throughput | Treat review capacity, not generation capacity, as the throughput-limiting resource when scheduling parallel agent work |
| A "novel" algorithm silently turns out to be a known-wrong technique in disguise | The model pattern-matched to a similar known problem instead of solving the actual novel one | Design the novel core yourself; use the model only for surrounding boilerplate, and treat any offered "solution" to a known-unprecedented problem with active suspicion |

---

## Tradeoffs & when NOT to use this taxonomy

- **Don't treat the eight categories as exhaustive or the boundaries as sharp.** A task can be security-adjacent without being category 3 outright (validating user input near an authz boundary, for instance), and the honest response to ambiguity is to round toward caution, not to argue the task doesn't technically qualify.
- **Don't apply blanket caution to everything and call it rigor.** The 2023-2024 "review everything with equal suspicion" default is itself a documented failure mode in this module's lineage — it doesn't scale, and treating routine, low-stakes generation with category-3-level scrutiny is how review capacity gets wasted on the cases that didn't need it, leaving less for the ones that do.
- **Don't use "the model is really good now" as a reason to skip the taxonomy.** The security pass-rate data shows this specific failure category has *stalled*, not improved, across the same period models got dramatically more capable at other things — capability and the specific failure modes here are not the same axis, and assuming they move together is exactly the mistake automation bias predicts.
- **Do use the taxonomy as a triage tool, not a universal veto.** The point is routing — category 3 gets a security reviewer, category 6 gets tests-first, category 4 gets a written spec first — not refusing to use agentic generation in these areas at all. Every "what to do instead" above still uses the agent, just with a different gate in front of it.
- **The honest counter-argument to name:** a team that applies this taxonomy rigorously will look slower than a team that doesn't, in the short term, on exactly the metrics (PRs merged, features shipped) that are easiest to report upward. The taxonomy's payoff is in incidents avoided, which is invisible until the incident that didn't happen — the same asymmetry that makes resilience engineering (`T21-resilience-catalogue`) chronically under-invested in relative to feature work.

---

## Interview questions

### Q1 — Give me the failure taxonomy. Don't just list categories, give me the symptom for each.
**Testing:** whether you have real observable symptoms or a vague list of topics.
**Answer:** Novel algorithms: confidently produces a known-but-wrong technique instead of the actual novel one, with no "I don't know" signal. Correctness proofs: a valid-looking proof from an unfaithful formalization — the proof is internally consistent, the premises are wrong. Security-critical: measured 86% pass rate on crypto specifically, so roughly 1 in 7 ships an insecure implementation that reads as ordinary code. Tacit requirements: the model fills the unstated gap with a plausible default instead of asking. Performance-critical loops: passes correctness review, reintroduces an allocation-in-a-loop pattern a profiler catches and a diff review doesn't. Large refactors with no tests: confident, silent behavior change with nothing mechanical to flag it. Unfamiliar domains: comprehension debt — readable but not evaluable. Regulated code: may be entirely correct and still fail because there's no auditable provenance trail.
**Follow-up trap:** *"Which of these eight is the most common in practice?"* — security-critical, by the numbers: a 44% overall vulnerability rate across categories and specifically-measured gaps in crypto (14%) and Java (71% failure) make this the category most likely to actually appear in a random sample of generated code, versus the others, which are more about task *type* than statistical frequency.

### Q2 — What's the actual decision rule underneath the eight categories, stated as one sentence?
**Testing:** whether you can compress the taxonomy to its generating principle.
**Answer:** Delegate when reviewing the output costs less than producing it yourself; don't when review costs more. Each of the eight categories is a specific reason review cost spikes — nothing to check a novel algorithm against, verifying a proof being as hard as deriving it, needing security expertise that's scarcer than the code was to write, and so on. The categories are instances, not a separate rule.
**Follow-up trap:** *"How do you estimate review cost before you've reviewed anything?"* — you can't precisely, but you can classify: does this task fall into one of the eight categories, yes or no. Category membership is itself the cheap, available signal that review cost is likely to spike, which is exactly why the taxonomy is useful as a gate even without a precise cost estimate.

### Q3 — Explain the review-cost inversion with real numbers.
**Testing:** whether the economic argument is concrete or hand-wavy.
**Answer:** Generation cost fell roughly two orders of magnitude over three years. Human comprehension speed of unfamiliar code did not improve at all over the same period — reading code is not a capability LLMs sped up, because it's not the LLM doing the reading. The reported shape in production: a feature generated in four minutes can require an hour of careful review. Two agents generating in parallel doesn't double throughput, it doubles the hour-long review queue, because the bottleneck moved entirely to the human side of the ratio.
**Follow-up trap:** *"Doesn't AI-assisted code review close that gap?"* — partially, for the mechanical parts (linting, import verification, pattern matching against known vulnerability classes) per `T27-reviewing-ai-code`. It does not close it for the categories in this taxonomy specifically, because the hard part of reviewing a novel algorithm, an unfamiliar domain, or a tacit requirement isn't mechanical pattern-matching, it's judgment the review tool doesn't have either.

### Q4 — What is automation bias, concretely, in the context of AI-generated code — and why is it the harder problem?
**Testing:** whether you separate "the code is wrong" from "the human ships it anyway."
**Answer:** 96% of developers report not fully trusting AI-generated code, yet only 48% consistently verify it before merging — a roughly 30-point gap between stated distrust and actual verification behavior. It's the harder problem because it doesn't improve as generation quality improves; even a model that got measurably better at avoiding all eight taxonomy categories would still ship incidents through this gap, because the failure is in the human review process — people correct an AI's output less when correcting it costs extra effort, which describes exactly the moment a reviewer decides a plausible-looking diff is probably fine.
**Follow-up trap:** *"How do you fix a bias, not a tooling gap?"* — process, not tooling: normalize "I could not verify this" as a complete, acceptable, blocking review comment rather than a personal failure requiring further investigation before you're allowed to raise it. The fix targets the social cost of admitting you didn't verify something, because that social cost, not a missing tool, is what the 30-point gap is measuring.

### Q5 — Your team wants to run three agents in parallel on three features to "go 3x faster." What's your pushback?
**Testing:** whether you apply the review-cost inversion to a scheduling decision, not just a single task.
**Answer:** If the review-cost inversion holds for any of the three (any of the eight categories present), running them in parallel doesn't produce 3x throughput, it produces 3x the review queue on the expensive side of the ratio — which is exactly the DORA-documented pattern (98% more PRs merged, review time up 91%, later up 441%, with 31% more merging unreviewed). Parallelizing generation without parallelizing review capacity just relocates the bottleneck and hides it behind a "features shipped" metric that doesn't count the debt.
**Follow-up trap:** *"So never parallelize?"* — no, parallelize freely when none of the three tasks falls into a taxonomy category and review cost is genuinely lower than write cost for all three; the pushback is specifically against parallelizing tasks where the inversion holds, not against parallel agent use as a pattern.

### Q6 — A refactor "looks clean" in review. What's missing from that sentence?
**Testing:** category 6 specifically, and whether "looks clean" registers as a red flag rather than reassurance.
**Answer:** Whether it's *behavior-preserving*, which "looks clean" says nothing about — a refactor reads exactly as confidently whether it silently changed behavior or not, and nothing about diff review mechanically checks semantic equivalence between two large versions of the same code. The missing artifact is characterization tests written *before* the refactor, which convert "does this preserve behavior" from a human holding two diffs in their head into a mechanical, automatable check.
**Follow-up trap:** *"The codebase has no test coverage and a refactor is overdue. Do you block on writing tests first?"* — yes, for anything beyond a small, easily-diffed change; a large refactor with no tests is a rewrite wearing a smaller diff, and the tests-first requirement isn't bureaucracy, it's the only mechanism that makes review cost tractable at all for this category.

### Q7 — When is it acceptable to say "I don't understand this well enough to review it"?
**Testing:** whether you treat this as a legitimate senior answer or a confession of weakness.
**Answer:** Whenever it's true, and treating it as legitimate is the actual countermeasure to category 7 and to automation bias generally. Comprehension debt is dangerous specifically because readable code creates false confidence that it's also reviewable — the fix isn't pushing through the discomfort and approving anyway, it's naming the gap and either escalating to someone who has the domain knowledge or investing the time to actually acquire it before shipping.
**Follow-up trap:** *"Won't that slow the team down constantly?"* — less than the alternative. The cost of admitting "I can't evaluate this" up front is a delay; the cost of approving something you couldn't actually evaluate is an incident with an unknown blast radius, discovered later, at a much worse time to discover it.

### Q8 — Design the review routing for a PR that touches both a performance-critical hot path and an authorization check.
**Testing:** whether you can apply the taxonomy compositionally, not just to single-category examples.
**Answer:** Two independent gates, both mandatory, neither substituting for the other: a security-trained reviewer for the authorization logic (category 3), and a benchmark run against the identified hot path's performance budget (category 5), run in CI as a hard gate rather than left to the security reviewer's judgment, since a security review passing says nothing about whether the code also regressed latency. Treating this as one review by one generalist reviewer is the mistake — the two categories need different expertise and different tooling, and combining them into a single pass is how one gets shortchanged.
**Follow-up trap:** *"What if you only have one reviewer available and a deadline?"* — split the PR if at all possible, ship the non-critical parts, and hold the authorization and hot-path changes for the reviewer/benchmark gate specifically, even if that means the deadline slips on the higher-risk portion. Compressing both categories into one rushed pass under deadline pressure is exactly the condition under which the 14%-insecure-crypto and silent-performance-regression symptoms actually surface in production.

### Q9 — Is this taxonomy a permanent list, or will some categories stop mattering as models improve?
**Testing:** whether you can distinguish capability-solvable gaps from structurally unsolvable ones.
**Answer:** Some categories are plausibly capability-solvable: security pass rates could rise with better training and pre-generation static verification, the way fabricated-API rates are already shrinking with import-checking tooling per `T27-reviewing-ai-code`. Others are structural, not capability gaps, and won't close no matter how good the model gets: tacit requirements are unwritten by definition, so no model can generate correctly against information that doesn't exist anywhere yet; novel algorithms have no training distribution to draw on by definition; provenance requires a human decision trail that generation doesn't produce regardless of quality. Automation bias in particular is a human-process failure and is explicitly orthogonal to model capability — it doesn't improve as the model does.
**Follow-up trap:** *"Which one are you most confident closes within two years?"* — security pass rates, tentatively, because the trend line (static verification moving pre-generation, per the lineage section) targets exactly the mechanically-checkable subset of that category. I'd flag this as the one prediction in this module I'd hold least confidently, given the track's own stated short shelf life.

### Q10 — What's the single most opinionated claim in this module, and defend it.
**Testing:** the closing-question pattern this track uses, applied to the module explicitly designed to be its most opinionated.
**Answer:** That automation bias, not model capability, is the actual root cause of most incidents that trace back to this taxonomy — the 96%-distrust-but-48%-verify gap means the categories in this module were, in a real sense, already known to the people who shipped the incident; they said out loud they didn't fully trust the output and approved it anyway. That reframes the fix: better models and better taxonomies both help at the margin, but the load-bearing fix is organizational — making "I could not verify this" a complete, socially acceptable, blocking review comment, because the gap this module is really about is between what people say they believe and what they do under review-time pressure.
**Follow-up trap:** *"Isn't that just restating 'code review is important,' dressed up?"* — no, and the distinction matters: "code review is important" doesn't explain why reviewers who *already* distrust the output still approve it. Automation bias explains the specific mechanism (correction cost is discounted, favorable attitude toward the tool overrides stated caution), which is what makes it a fixable, specific target rather than a generic exhortation to review more carefully.

---

## Red flags that fail you

- A generic "AI code should always be reviewed carefully" answer with no named categories or symptoms.
- Treating all eight categories as equally common rather than knowing security-critical is the statistically dominant one.
- No numbers — citing "AI code has bugs" without the 44%/86%/14%/29% figures that make the security category concrete.
- Believing better models close every category on this list, including the structural ones (tacit requirements, novel algorithms, provenance).
- Not distinguishing automation bias (a human process failure) from generation quality (a model failure) as separate problems requiring separate fixes.
- Recommending blanket "review everything with maximum suspicion" as if that isn't itself a documented, unscalable failure mode.
- No answer for what to do *instead* in a flagged category — refusing to delegate isn't a complete answer without a next step.
- Treating "the diff looked clean" as evidence of anything, for a refactor or a security-critical change specifically.

## Cheat card

```
THE RULE: delegate iff review_cost < write_cost. every category below is a
  reason review cost spikes for a specific kind of task.

THE EIGHT, with the symptom (not just the name):
  1 NOVEL ALGORITHM    confidently produces a known-WRONG technique, no
                        "I don't know" signal (no training distribution to match)
  2 CORRECTNESS PROOF  valid-looking proof, UNFAITHFUL formalization --
                        verifying it = re-deriving it yourself
  3 SECURITY-CRITICAL  crypto 86% pass (~1/7 insecure) · overall 56% pass,
                        ~44% fail rate · Java worst at 29% pass · authz
                        misconfig = most common backend failure class
  4 TACIT REQUIREMENTS model fills gaps with a PLAUSIBLE default, doesn't ask
  5 PERF-CRITICAL LOOP passes correctness review, reintroduces alloc-in-loop /
                        nested-loop patterns a PROFILER catches, diff review doesn't
  6 LARGE REFACTOR,    confident SILENT behavior change, nothing mechanical
    NO TESTS           flags it
  7 UNFAMILIAR DOMAIN  comprehension debt: readable != reviewable
  8 REGULATED/         may be CORRECT and still fail -- no auditable
    PROVENANCE         requirement->implementation trail

REVIEW-COST NUMBERS: generation ~100x cheaper over 3 years; human code-reading
  speed: UNCHANGED over the same period. 4-min generate can cost 1hr review.
  parallel agents MULTIPLY the review queue, don't multiply throughput.
  (DORA: 98% more PRs merged, review time +91% -> +441%, 31% merge unreviewed)

AUTOMATION BIAS (the harder problem, ORTHOGONAL to model capability):
  96% don't fully trust AI code · only 48% consistently verify before merge
  ~30pp gap between STATED distrust and ACTUAL verification behavior
  people correct less when correction costs extra effort -- general finding,
  not code-specific. doesn't improve as models improve.

WHAT TO DO INSTEAD (never just "refuse" -- route, don't block outright):
  1,2 -> design/derive yourself, model for boilerplate only
  3   -> security-trained reviewer, mandatory, no "diff looked small" exception
  4   -> write the requirement down FIRST; can't write it = doesn't exist yet
  5   -> benchmark gate in CI on identified hot paths, independent of code review
  6   -> characterization tests BEFORE refactor, hard precondition
  7   -> get a domain expert, or admit "I can't evaluate this" -- legitimate, not weak
  8   -> capture provenance AS workflow output (ADRs), not reconstructed after

CATEGORY MEMBERSHIP = HARD GATE, not averaged with other factors (same
  disqualification logic as T28-harness-comparison's scoring rubric).

WHEN NOT TO APPLY: don't blanket-suspicion EVERYTHING (that's the pre-2024
  failure mode, doesn't scale, wastes review capacity on low-stakes work).
  taxonomy = triage tool, not universal veto -- every category still has a
  "what to do instead" that still uses the agent, with a different gate.
```

## Sources

- [AI-generated code security has stalled at 56%](https://thenextweb.com/news/veracode-2026-genai-code-security-56-percent-pass-rate) — Veracode 2026, overall pass-rate stagnation; accessed 2026-08-01
- [AI Coding Security Vulnerability Statistics 2026](https://sqmagazine.co.uk/ai-coding-security-vulnerability-statistics/) — 86% crypto pass rate, Java 29% pass rate, authz misconfiguration as most common failure; accessed 2026-08-01
- [Code Is Cheap. Review Is Expensive.](https://blog.kilo.ai/p/code-is-cheap-review-is-expensive) — the ~100x generation cost drop vs unchanged review speed, the 4-minute-generate/1-hour-review shape, parallel-agents-multiply-the-queue argument; accessed 2026-08-01
- [Testing for Automation Bias in AI Systems](https://medium.com/@kaylenstuart/testing-for-automation-bias-in-ai-systems-when-humans-trust-machines-a-little-too-much-d2c685289b5f) — the 96%-distrust/48%-verify gap; accessed 2026-08-01
- [Do LLMs Game Formalization? Evaluating Faithfulness in Logical Reasoning](https://arxiv.org/pdf/2604.19459) — proof validity vs formalization faithfulness, reviewer-panel limits; accessed 2026-08-01
- [PERFOPT-Bench: Evaluating Coding Agents on Software Performance Optimization](https://arxiv.org/pdf/2607.07744) — performance-regression patterns in generated code, few-shot mitigation limits; accessed 2026-08-01
- `curriculum/27-tooling-debugging/07-reviewing-ai-code.md` — the confidence-carries-no-evidentiary-weight foundation this module applies to novel algorithms, proofs, and refactors specifically
- `curriculum/28-ai-assisted-architecture/09-claude-architect.md` — the DORA review-time and PR-volume figures this module's review-cost inversion explains mechanically
- `curriculum/28-ai-assisted-architecture/08-ai-arch-review.md` — the provenance/ADR discipline this module's category 8 depends on

## Changelog
- 2026-08-01 — created
