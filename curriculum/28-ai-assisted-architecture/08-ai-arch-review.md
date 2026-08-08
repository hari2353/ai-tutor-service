# Using Agents for Architecture Review, ADRs, and Design Docs

> **Track:** T28 AI-Assisted Architecture (Claude) · **Time:** 2.0h · **Prereqs:** none · **Updated:** 2026-08-01
> **Module id:** `T28-ai-arch-review` · **Tags:** architecture

## The 30-second version

An agent is genuinely good at three architecture-adjacent jobs: finding inconsistency across a codebase larger than a human will re-read before every review, enumerating missing cases against a stated contract, and drafting the first version of a document from a messy source — a Slack thread, a design meeting transcript, or the codebase itself. It is not good at the one job architecture review actually is: judging whether a tradeoff is right for *this* org, *this* team's on-call load, *this* company's risk tolerance, because that judgment is loaded with context the agent was never shown and cannot ask for reliably — the outage eighteen months ago, the political compromise behind the current design, the customer who will churn over a specific latency regression. An agent drafting a design doc from your codebase has a specific, named failure mode: it describes what the code *looks like* it does, fluently and confidently, which is a different claim from what the code actually does, and the two diverge exactly where the code is subtle, buggy, or stale relative to its own comments. The workable split is mechanical: agent drafts, human decides, and the decision itself — not the drafting, not the formatting, not the enumeration of options — is the one thing that does not delegate. Put that split in writing as an ADR template with an explicit "Decision" field a human signs, and use the agent adversarially, as a second reviewer of its own or a colleague's design, never as the only reviewer of anything irreversible.

## Why this gets asked

Because by 2026 "have the agent write the design doc" is the reflex, and the interviewer has watched it go wrong in a specific, recoverable way: a design doc that reads as authoritative, cites the right file paths, and describes an architecture that stopped existing three refactors ago, because the agent generated it from a prompt and a skim rather than from ground truth, and nobody caught it before three engineers built against it. They have also watched the ADR version of the same failure: a beautifully formatted decision record for a decision nobody with the authority to make it actually reviewed, because the agent produced something so complete-looking that the human rubber-stamped it. What they are testing is whether you know the boundary between "the agent can produce this artifact" and "the agent can be trusted as the source of the judgment inside it" — and whether you would put your name on a decision an agent wrote unread.

---

## Lineage: past → present → future

**What came before.** Design docs and ADRs are a mid-2010s formalization — Michael Nygard's ADR post (2011) gave the pattern a name, and Google's and Amazon's internal design-doc cultures spread the practice of writing the doc before the code specifically because the pain it fixed was expensive: architecture decisions made in a meeting with no record, re-litigated eighteen months later by an engineer who wasn't in the room, with nobody able to say whether the original tradeoff still held. The discipline these documents encode long predates AI: write down the decision and the reasoning while the reasoning is still fresh, so a future reader gets the "why," not just the "what." The pain that never went away was authoring cost — a properly reasoned ADR with alternatives considered took real time, so teams either wrote them for major decisions only or let the practice lapse under deadline pressure, and the ADR folder in most repos is a graveyard of the first six months after the team read a blog post about ADRs.

**Where it stands now.** Generation cost collapsed and the practice consolidated around "agent drafts, human decides." A first-draft ADR from a natural-language description of the decision now takes minutes rather than the 30-40 minutes of manual writing it used to cost ([Codex CLI Architecture Decision Records, accessed 2026-08-01](https://codex.danielvaughan.com/2026/04/28/codex-cli-architecture-decision-records-adr-automated-governance/)), and the live pattern is continuous rather than occasional: teams add an ADR policy to their agent instructions file (`AGENTS.md`/`CLAUDE.md`) directing the agent to check the ADR folder before proposing an architectural change and draft a new one before implementing it, and a review agent flags PRs that contradict an already-accepted decision. That consolidation is real progress on authoring cost and it does not touch the harder problem, which is also now well documented: architecture review specifically is where agents are weakest among review categories, because "a reviewer who lived through the last outage may know why a seemingly cleaner abstraction was rejected six months ago, whereas the agent sees code and comments" but not "the incident call, the customer escalation, and the political compromise behind the current design" ([Adversarial Code Review, Augment Code, accessed 2026-08-01](https://www.augmentcode.com/guides/adversarial-code-review)). The live disagreement is scope: one camp treats the agent as a drafting tool only, gated by a human "Decision" field that must be filled by a named person; the other is already running review agents that approve or block PRs against ADR conformance automatically, which works for mechanical conformance (does this PR touch a module the ADR says is frozen) and does not work for "was the ADR itself the right call," a question no agent in that pipeline is positioned to ask.

**Where it's heading.** High confidence: doc-code drift detection moves into CI as a mechanical, non-negotiable gate, the same way test coverage did — a documentation freshness check comparing docs against the commits and interfaces they describe, triggered on merge, flagged as a build failure rather than a someday-cleanup task, motivated by the same velocity problem coding agents created generally: GitHub recorded roughly 986 million commits in 2025, and more commits from more agent-assisted PRs means faster, not slower, drift ([Stop Documentation Drift, accessed 2026-08-01](https://earezki.com/ai-news/2026-06-13-confluence-docs-lie-tie-your-documentation-to-code-instead/)). Medium confidence: adversarial review — a second model, ideally from a different family, reviewing the first model's design output with no access to the first model's reasoning — becomes the default configuration for any AI-assisted design review, for the same reason "the maker shouldn't grade the checker" is already established for code review (`T27-reviewing-ai-code` and the adversarial-review literature this module extends to architecture). Speculative: whether "the agent flags PRs that contradict accepted ADRs" scales past the mechanical-conformance case into anything resembling actual judgment about whether the ADR still holds; the honest read of the 2026 evidence is that this stays a search-and-flag tool, not a decision-maker, for the foreseeable future.

---

## Mental model

```
                 GOOD AT (agent)                    BAD AT (agent)
   ┌──────────────────────────────────┐   ┌──────────────────────────────────┐
   │ Consistency across a codebase     │   │ Whether THIS tradeoff is right   │
   │ larger than you'll re-read        │   │ for THIS org's risk tolerance    │
   │                                    │   │                                    │
   │ Enumerating missing cases against │   │ The political compromise behind  │
   │ a stated contract                 │   │ why the current design exists    │
   │                                    │   │                                    │
   │ First-draft ADR/design doc from a │   │ The incident eighteen months ago │
   │ transcript, thread, or codebase   │   │ that makes "obviously better"    │
   │                                    │   │ actually mean "we tried that"    │
   │ Finding drift: doc says X,        │   │ Owning the DECISION, at all,     │
   │ code does Y                       │   │ ever                             │
   └──────────────────────────────────┘   └──────────────────────────────────┘

   THE PIPELINE THAT RESPECTS THE SPLIT:

   source material ──▶ AGENT DRAFTS ──▶ HUMAN DECIDES ──▶ signed ADR
   (thread, code,        (structure,      (fills the         (accountability
    transcript)           options,         "Decision" field    line: a name,
                           tradeoffs        with a NAME,        not a model,
                           enumerated)      can reject          owns it)
                                            entirely)
```

The one-sentence version: **an agent can produce every part of an ADR except the word "Decided," and that word is the only one anyone will hold you accountable for.**

---

## How it actually works

### 1. What the agent is genuinely good at, with the mechanism named

- **Consistency checking at a scale you won't re-read.** Given a stated invariant ("all mutating tools must be idempotent" — `T28-mcp-authoring`), an agent can grep and read every tool definition in a codebase and report which ones violate it, which is exhaustive search, not judgment. This is the same mechanism `T07-harness-engineering`'s computational-versus-inferential control distinction names: exhaustive checking against an explicit rule is a computational control and agents are reliable at it precisely because it doesn't require judgment.
- **Missing-case enumeration against a contract.** "Here is the API's stated error taxonomy; which endpoints don't handle `409`?" is the same shape of question and the same mechanism.
- **Drafting from noisy source material.** A design meeting transcript, a Slack thread arguing three options, or a half-written doc becomes a structured first draft in minutes instead of the 30-40 minutes of manual ADR writing it used to cost. The value is real and it is entirely about *authoring speed*, not about the quality of the underlying judgment — the agent structures a decision that was already made in the room; it does not make one.
- **Cross-referencing a large codebase for drift**, covered in detail below.

### 2. What it is not good at, and why the failure isn't a prompting problem

The tradeoff-judgment failure is not fixable by asking more clearly. An agent has no access to: the outage that killed the "obviously better" alternative, the team's actual on-call load and appetite for operational complexity, the customer contract that makes a specific latency number non-negotiable, or the six-month-old political compromise that explains why the current design looks worse than it is. These are not facts that live in the codebase or the conversation — they live in institutional memory, and an agent asked to "evaluate whether this architecture is right for us" will produce a plausible-sounding evaluation using general principles (CAP theorem tradeoffs, coupling arguments, cost estimates) that reads exactly as confidently whether or not it matches the actual constraint that matters here. This is the same "confidence carries zero evidentiary weight" property `T27-reviewing-ai-code` documents for generated code, applied to generated judgment instead of generated syntax.

### 3. ADR structure: agent drafts, human decides

A working ADR template that encodes the split explicitly rather than leaving it implicit:

```markdown
# ADR-014: Move session storage from sticky Redis to a stateless JWT

## Status
Proposed          <!-- agent can set this -->

## Context
[Agent-drafted from the discussion thread / codebase, including the
current design, the pain driving the change, and constraints (latency
budget, team size, existing infra).]

## Options considered
[Agent-drafted: at least two real alternatives, not a strawman and the
chosen option. Each with a one-line cost.]

## Decision
[**BLANK until a named human fills it in.** Not "we will move to
stateless JWT" written by the agent — a sentence with a name attached:
"Decided by @priya, 2026-08-01: move to stateless JWT because the
on-call cost of sticky-session debugging during an incident outweighs
the token-revocation complexity, which we mitigate with a 5-minute
TTL." The reasoning restates constraints the agent could not have
weighed on its own.]

## Consequences
[Agent can draft the mechanical ones — what breaks, what needs a
migration — but the human decision-maker should add the consequence
that's actually a bet: "we're accepting that revocation takes up to
5 minutes, which is a regression from instant session kill."]
```

The load-bearing design choice is that **"Decision" is a field with a required name, not a field the agent fills in with confident prose.** This is the direct architectural expression of `T28-claude-architect`'s Level 1/2/3 control distinction applied to a document instead of code: a norm that says "a human should decide" is Level 1 (instruction, ignorable); a template with a mandatory attributed field and a CI check that a merge referencing an ADR fails if that field is empty is Level 3 (enforcement).

### 4. Design-doc generation from a codebase, and its named failure mode

**Failure mode: confident-description drift.** Ask an agent to "write a design doc for how the auth module works" from the codebase alone, and it produces a document that describes what the code *looks like* it does — the shape suggested by names, comments, and the common pattern the code superficially resembles — rather than what it actually does. The observable symptom: the generated doc is internally coherent, well-organized, and cites real file paths and function names, and it is wrong in exactly the places where the code is subtle (an edge case handled differently than the function name implies), buggy (a comment describing intended behavior that a later patch silently broke), or stale (a code path that used to matter and is now dead but still reads as load-bearing). This is structurally the same failure `T27-reviewing-ai-code` documents for generated code review — a model's fluency is uncorrelated with whether the underlying claim is true — applied to generated documentation about existing code instead of generated code itself.

The fix is not a better prompt. It is treating agent-generated design docs the way you'd treat an intern's first-week writeup of a system they didn't build: useful as a structured starting point, worthless as ground truth until someone who actually understands the subtle parts reads it line by line and either confirms or corrects each claim against the real code path, ideally by writing or running a test that would fail if the doc's claim were wrong.

### 5. Adversarial design review

The core problem, stated precisely: **a model reviewing its own design output is not checking the design against reality, it is checking whether the design looks like the kind of thing that gets generated correctly** ([Adversarial Code Review, accessed 2026-08-01](https://www.augmentcode.com/guides/adversarial-code-review)). The model that rationalized a shortcut while drafting will rationalize the same shortcut while reviewing, because it is the same weights making structurally the same judgment call twice.

The mitigation, extended from code review to architecture review:

- **A different model family reviews**, not the same model in a second pass. Cross-model adversarial review specifically targets the case where one model's blind spots are systematic rather than random — an error mode common to a model family will not be caught by another instance of the same family.
- **The reviewer gets read-only access and no shared context with the author's reasoning.** Feeding the reviewer the drafting model's chain of thought defeats the purpose; it should evaluate the artifact (the ADR, the design doc) cold, the way a human reviewer who wasn't in the design meeting would.
- **The reviewer's job is enumerated risk, not approval.** "What could go wrong with this design, list every failure mode you can find" produces a longer, more useful list than "is this design good," which invites agreement.
- **The human still owns the decision.** Adversarial review improves the *drafting* quality by surfacing more of the disagreement space before a human looks at it; it does not relocate the decision. Two models disagreeing is evidence for the human to weigh, not a vote that resolves itself.

### 6. Finding drift between docs and implementation

This is the strongest "good at" case in this module because it reduces to exhaustive search, which is exactly the mechanism named in section 1. Concretely:

1. Extract every factual claim from a doc that's checkable against code: "the retry limit is 3," "this endpoint is idempotent," "sessions expire after 30 minutes."
2. For each claim, have the agent locate the actual implementation and report whether it matches, with the file and line as evidence — never a bare "yes/no," because the evidence is what makes the claim auditable by a human afterward.
3. Flag claims the agent could *not* verify (the implementation moved, the described behavior is config-driven and the config wasn't checked) as a distinct category from confirmed drift, because silently treating "couldn't verify" as "matches" reintroduces the confident-description failure one layer up.

The economic case for doing this continuously rather than occasionally: documentation issues are estimated to cost a 50-person engineering team upward of $200K a year in wasted clarification time and decisions made against stale information ([Documentation Drift, accessed 2026-08-01](https://earezki.com/ai-news/2026-06-13-confluence-docs-lie-tie-your-documentation-to-code-instead/)), and that cost compounds under agent-assisted development specifically because commit velocity is higher — more PRs merging, more surface area for a doc to fall out of sync, faster.

### 7. The accountability line

State it as a rule, because it is the one sentence worth memorizing from this module: **the agent does not own the decision, at any point in the pipeline, regardless of how good its draft was.** This is not a statement about current model capability that will age out — it's a statement about where accountability has to live in an organization. A wrong architectural bet has consequences (an outage, a costly migration, a missed deadline) that land on a person's performance review and a team's on-call rotation, and "the agent recommended it" is not an answer to "why did we do this" that any organization accepts. `T28-claude-architect` makes the general version of this argument for AI-assisted engineering; here it is specific: an ADR or design doc with no named human decision-maker is not a governance artifact, it's a transcript with a title.

---

## Build it from scratch

A minimal doc-drift checker, exercising the "exhaustive search, not judgment" mechanism directly:

```python
# untested sketch — illustrates the pattern, not a shipped tool
import re
from dataclasses import dataclass

@dataclass
class Claim:
    doc_path: str
    line: int
    text: str
    check: str          # what to grep/verify in code

@dataclass
class DriftResult:
    claim: Claim
    verified: bool | None   # None = could not verify, NOT the same as False
    evidence: str

CLAIM_PATTERNS = [
    (r"retry.*?(\d+)\s*times?", "retry_limit"),
    (r"expires? after (\d+)\s*(minute|hour)s?", "expiry"),
    (r"idempotent", "idempotency_marker"),
]

def extract_claims(doc_text: str, doc_path: str) -> list[Claim]:
    claims = []
    for i, line in enumerate(doc_text.splitlines(), 1):
        for pattern, check in CLAIM_PATTERNS:
            if re.search(pattern, line, re.I):
                claims.append(Claim(doc_path, i, line.strip(), check))
    return claims

def verify_claim(claim: Claim, codebase_search) -> DriftResult:
    """codebase_search is the agent's actual grep/read capability, called
    here as a stand-in — the point is the loop's structure, not this fn."""
    hits = codebase_search(claim.check)
    if not hits:
        return DriftResult(claim, None, "no matching implementation found")
    matches = hits[0].confirms(claim.text)
    return DriftResult(claim, matches, hits[0].evidence)

def audit(doc_text: str, doc_path: str, codebase_search) -> list[DriftResult]:
    return [verify_claim(c, codebase_search) for c in extract_claims(doc_text, doc_path)]
```

The design point worth calling out: `verified` is `bool | None`, not `bool`, because collapsing "could not verify" into "matches" is exactly the confident-description failure this module is about, just moved into the tool that's supposed to catch it.

---

## How it's done in production

| What production adds | Why it matters |
|---|---|
| **ADR policy in the agent instructions file** | `AGENTS.md`/`CLAUDE.md` directs the agent to check `docs/adrs/` before proposing an architectural change and draft a proposed ADR before implementing, making the practice continuous instead of only-when-remembered |
| **CI-gated "Decision" field** | A merge referencing a new ADR fails if the `Decision` field is empty or unattributed — the Level 3 enforcement version of "a human should decide" |
| **Doc-drift check as a CI gate** | Triggered on merge, comparing docs against the interfaces/commits they describe, flagged as a build failure rather than backlog debt, the same posture as a test-coverage gate |
| **Cross-model adversarial review for irreversible designs** | A different model family reviews cold, with read-only access, producing an enumerated risk list rather than an approval |
| **PR-conformance-to-ADR bots** | Flags a PR that touches a module an ADR says is frozen, or contradicts an accepted decision — reliable for mechanical conformance, not for judging whether the ADR itself still holds |

### What breaks at scale

| Symptom | Cause | Fix |
|---|---|---|
| Three engineers build against a design doc that describes a system that no longer exists | Doc generated once from a codebase skim, never re-verified, code moved on | Doc-drift check as a CI gate, not a one-time artifact; treat unverifiable claims as a distinct flagged category |
| An ADR gets treated as final because it "looks complete" | Agent produced polished prose for the Decision field; nobody with authority actually decided | Require a named human in the Decision field; CI-fail an empty or unattributed one |
| Agent-reviewed design gets approved with a serious flaw a human later finds in production | Same model drafted and reviewed; rationalized the same shortcut twice | Cross-model adversarial review with no shared reasoning context, read-only, enumerated-risk framing |
| "The agent said the architecture was sound" used as the justification for a bad outcome | Confused an agent's confident description with a judgment about organizational fit | State the accountability line explicitly: agent drafts, named human decides and owns it |
| Drift-detection tool reports 100% doc accuracy, still wrong in production | Tool collapsed "could not verify" into "matches" | Track unverifiable claims separately; audit them manually, don't default them to true |
| Review agent approves every PR that superficially matches ADR keywords | Conformance check is textual, not semantic — "mentions Redis" instead of "obeys the sticky-session prohibition" | Encode the actual invariant as a checkable rule (`T28-mcp-authoring`'s consistency-check mechanism), not a keyword match |

---

## Tradeoffs & when NOT to use an agent here

- **Don't let an agent produce the only review of an irreversible architectural decision.** A migration that's expensive to reverse (a data-model change, a vendor lock-in, a security-boundary redesign) needs a human who has weighed the org-specific cost, not a plausible-sounding evaluation using general principles.
- **Don't treat a generated design doc as ground truth without line-by-line verification against the actual code paths it describes**, especially for the subtle, buggy, or stale parts — those are exactly where confident-description drift concentrates, because they're where the code diverges most from what its own names and comments suggest.
- **Don't use same-model self-review for anything that matters.** If the review budget only allows one pass, spend it on a human, not a second call to the same model that drafted the design — a second pass from the same weights is not independent evidence.
- **Don't skip the accountability line because the artifact is "just documentation."** An ADR with no named decision-maker is the governance failure mode this whole module exists to prevent, and it's cheap to fix (a required field, a CI check) relative to the cost of the decision it's supposed to record.
- **Do use the agent aggressively for drafting, drift-finding, and enumeration** — these are the tasks where exhaustive, tireless, unbiased-by-institutional-memory search is a genuine advantage over a human doing the same check for the fourth time this quarter.

---

## Interview questions

### Q1 — What is an agent genuinely good at in architecture review, and what is it not?
**Testing:** whether you have a principled split or a vague "AI helps with docs" answer.
**Answer:** Good at exhaustive, mechanical checks: consistency against a stated invariant across a large codebase, missing-case enumeration against a contract, first-draft structure from noisy source material, and drift detection between docs and code. Not good at judging whether a tradeoff is right for this specific org, because that judgment depends on institutional memory the agent was never shown — the outage that killed an alternative, the team's actual on-call appetite, a customer contract's non-negotiable latency number.
**Follow-up trap:** *"Isn't that just a training-data gap you can fix with a better prompt?"* — no, because the missing information doesn't exist in any text the agent could be shown; it lives in people's memory of events, not documents. Prompting more clearly doesn't manufacture institutional context that was never written down.

### Q2 — Design an ADR template for AI-assisted drafting. What's the one field that matters most?
**Testing:** whether you land on the accountability mechanism unprompted.
**Answer:** "Decision," and it must require a named human, not agent-generated prose. Context, Options Considered, and the mechanical parts of Consequences can all be agent-drafted from the discussion or codebase; the Decision field is the one place the org's actual judgment has to appear, attributed to a person who can be asked about it later.
**Follow-up trap:** *"How do you enforce that in practice, not just as a norm?"* — a CI check that fails a merge referencing a new or modified ADR if the Decision field is empty or has no attributed name. A norm in a template is Level 1 instruction and gets skipped under deadline pressure; a CI gate is Level 3 enforcement, per `T28-claude-architect`'s control-level distinction.

### Q3 — An agent generates a design doc for an existing module. What's the specific failure mode to watch for?
**Testing:** whether you know the named failure or just say "it might be wrong."
**Answer:** Confident-description drift: the doc describes what the code *looks like* it does based on names, comments, and superficial pattern-matching, rather than what it actually does, and it does so fluently and coherently. The doc is wrong exactly where the code is subtle, buggy, or stale relative to its own comments — precisely the places where a design doc is most valuable and most dangerous to get wrong.
**Follow-up trap:** *"How would you catch this in review?"* — treat every factual claim in the doc as independently checkable against a real code path or test, not as a unit to approve wholesale. A doc that's 90% accurate and 10% confidently wrong in the subtle parts is more dangerous than a doc that's honestly incomplete, because nothing about its tone signals which 10%.

### Q4 — Why is "have the model review its own design" a weak review strategy?
**Testing:** the self-review structural argument, not just "models make mistakes."
**Answer:** A model reviewing its own output isn't checking the design against reality, it's checking whether the design looks like the kind of thing that gets generated correctly — the same weights that rationalized a shortcut while drafting will rationalize it again while reviewing, because it's structurally the same judgment call made twice by the same process.
**Follow-up trap:** *"So a second call to the same model with a 'be critical' instruction fixes it?"* — no, for the same reason: it's still the same model's judgment, just prompted to sound more skeptical, which changes the tone of the review, not its independence. Real independence requires a different model family with no shared reasoning context and read-only access, evaluating the artifact cold.

### Q5 — How do you detect drift between a design doc and the actual implementation, mechanically?
**Testing:** whether you can turn "drift" into a checkable procedure.
**Answer:** Extract every factual, checkable claim from the doc (a specific limit, a specific behavior, a specific guarantee), locate the actual implementing code for each, and report a match/mismatch with the file and line as evidence — never a bare yes/no. Critically, track claims that could not be verified (moved code, config-driven behavior not inspected) as a separate category from confirmed matches, because collapsing "couldn't check" into "matches" reintroduces the exact confident-description failure the check exists to catch.
**Follow-up trap:** *"What's the ROI case for running this continuously versus occasionally?"* — documentation issues cost a 50-person engineering team upward of $200K a year in stale-information overhead, and agent-assisted development increases commit velocity, which increases drift *faster*, not slower, so an occasional check falls further behind every cycle. A CI-gated check on merge, the same posture as test coverage, is the only version that keeps pace.

### Q6 — Your team wants a bot that auto-approves PRs conforming to accepted ADRs. What's the risk?
**Testing:** whether you distinguish mechanical conformance from actual judgment.
**Answer:** It's reliable for mechanical conformance — flagging a PR that touches a module an ADR explicitly says is frozen, or that reintroduces a pattern an ADR rejected by name. It is not positioned to judge whether the underlying ADR still holds, because that's the same tradeoff-judgment problem this whole module is about, just moved one level up: an agent can check "does this PR match the decision" but not "was the decision still right eighteen months later."
**Follow-up trap:** *"What would make you revisit an ADR?"* — a mechanism outside the conformance bot entirely: a periodic human review of ADRs whose stated context (traffic pattern, team size, cost assumption) has materially changed, which is exactly the kind of judgment call that needs institutional memory the bot doesn't have.

### Q7 — Someone says "the agent said the architecture was sound, so we shipped it." Where did this go wrong?
**Testing:** the accountability-line question stated as a scenario.
**Answer:** Before it shipped: an agent's assessment was treated as a decision instead of an input to one. The agent can draft an evaluation using general architectural principles, but "sound" for this specific org's risk tolerance, on-call capacity, and cost structure is a judgment nobody delegated correctly if the answer to "who decided this" is "the agent."
**Follow-up trap:** *"Is this fixable with a better agent, going forward?"* — no, and saying so is the point. This isn't a capability gap that improves with a stronger model; it's a governance gap. The fix is procedural: a named human decision-maker required on every architectural artifact, regardless of how good the drafting agent gets.

### Q8 — Compare an agent-drafted ADR to a human-written one from five years ago. What's actually different?
**Testing:** whether you can name the real change versus the superficial one.
**Answer:** Authoring speed and completeness of the draft — options enumerated, context assembled from a scattered thread, formatting consistent — dropped from roughly 30-40 minutes of manual writing to a few minutes. What has not changed is what the document is *for*: recording a decision and its reasoning so a future reader doesn't re-litigate it blind. The Decision field still needs the same thing it always needed, a person who actually weighed the org-specific tradeoff, and that part got neither faster nor slower, because it was never a drafting problem.
**Follow-up trap:** *"So there's no real change to the ADR practice itself?"* — one real change: the low authoring cost means teams can now afford ADRs for decisions they used to skip documenting, which is a genuine improvement in documentation coverage, not a change in what a Decision field needs to contain.

### Q9 — How would you structure an adversarial review for a major schema-migration design?
**Testing:** whether you can operationalize the concept, not just define it.
**Answer:** A different model family than the one that drafted the design, given the design document cold with no access to the drafting model's reasoning trace, instructed to enumerate every failure mode it can find rather than render an approve/reject verdict — "what could go wrong" produces a longer and more useful list than "is this good," which invites agreement. The output is a risk list a human decision-maker weighs alongside their own judgment; two models disagreeing is evidence to consider, not a tiebreaker that resolves the decision automatically.
**Follow-up trap:** *"What if both models agree the design is fine?"* — agreement between two models is weaker evidence than it sounds, because both may share the same blind spot if the failure mode is common to how models reason about migrations generally (for instance, underweighting operational cost during the migration window versus the steady state after). Institutional memory — has this team done a migration like this before, and what broke — is still a human check neither model result substitutes for.

### Q10 — What's the single highest-leverage thing you'd automate first in an architecture-review pipeline?
**Testing:** prioritization under the "agent drafts, human decides" constraint.
**Answer:** Doc-code drift detection as a CI gate, because it's the purest instance of the mechanism agents are actually reliable at — exhaustive checking of a factual claim against a real code path — and because letting it lapse costs real money continuously (the $200K/year figure for a 50-person team) rather than costing a single bad decision once. It's also the lowest-risk automation on the list: a false positive costs a human two minutes to dismiss, and a false negative is no worse than the status quo of nobody checking at all.
**Follow-up trap:** *"Why not automate the ADR Decision field next?"* — because that's the one part of the pipeline this module argues should never be automated, at any point, regardless of the marginal convenience. Prioritizing automation of the accountability mechanism itself, rather than protecting it, is the mistake this whole module is warning against.

### Q11 — How do you know whether an agent-generated design doc is trustworthy enough to build against?
**Testing:** a practical verification standard, not a vague "review it carefully."
**Answer:** Line-by-line verification of every checkable claim against the actual code, treated the way you'd treat an intern's first-week writeup of a system they didn't build — useful as structure, worthless as ground truth until confirmed. The concrete bar: for any claim that would change how a downstream team builds against this system (a guarantee, a limit, an invariant), there should be a test or a direct code citation confirming it before anyone relies on it, not just agent confidence that it's accurate.
**Follow-up trap:** *"That sounds like it costs as much as writing the doc yourself. What did you actually save?"* — the structuring and first-pass assembly, which is real time saved, especially for a doc synthesizing a scattered discussion. What you did not save, and should not try to save, is the verification cost for anything load-bearing — that cost was never the doc-writing time, it was always the understanding-the-system time, and an agent cannot do that part on your behalf.

---

## Red flags that fail you

- Treating an agent-generated design doc as ground truth without verifying its claims against actual code.
- An ADR with no named human in the Decision field, or a Decision field filled by the agent.
- Using the same model to draft and review a design with no independent check.
- Saying "the agent said the architecture was sound" as if that settles a tradeoff judgment.
- No answer for what an agent is *not* good at in this space.
- Believing PR-conformance-to-ADR automation means nobody needs to revisit whether the ADR still holds.
- Collapsing "could not verify this claim" into "this claim is true" in a drift-detection tool.
- No mechanism enforcing the human-decides step beyond a norm or a comment.

## Cheat card

```
GOOD AT: consistency checks (exhaustive, computational) · missing-case enumeration
  vs a stated contract · first-draft ADR/design doc from noisy source material ·
  drift detection between docs and code (also exhaustive search)

NOT GOOD AT: whether a tradeoff is right for THIS org -- needs institutional
  memory (the outage, the political compromise, the customer contract) the
  agent was never shown and cannot reliably ask for

ADR TEMPLATE: Context + Options (agent-draftable) -> DECISION (human, NAMED,
  required, CI-gated if empty) -> Consequences (mechanical parts agent-draftable,
  the "bet" consequence is the human's)
  first-draft time: ~30-40min manual -> few minutes agent-assisted

FAILURE MODE: confident-description drift -- agent-generated doc describes what
  code LOOKS LIKE it does (names/comments/pattern) not what it ACTUALLY does.
  wrong exactly where code is subtle/buggy/stale. same tone whether right or wrong.

ADVERSARIAL REVIEW: different MODEL FAMILY, no shared reasoning context,
  read-only, "enumerate every failure mode" not "is this good" (invites agreement)
  same-model self-review = checking if it LOOKS generated correctly, not vs reality

DRIFT DETECTION MECHANICS: extract checkable claims -> verify each against real
  code w/ file+line evidence -> track UNVERIFIABLE as separate from CONFIRMED
  (collapsing unverifiable into "matches" = the same failure, one layer up)
  cost of NOT doing this continuously: ~$200K/yr for a 50-person team (docs debt)
  986M GitHub commits in 2025 -> agent-assisted velocity makes drift compound faster

ACCOUNTABILITY LINE: the agent does not own the decision, ever, regardless of
  draft quality. Level 1 instruction (norm) != Level 3 enforcement (CI-gated
  required named field). An ADR with no named decider is a transcript, not
  a governance artifact.

WHEN NOT TO: irreversible decisions reviewed only by an agent · design docs
  relied on without line-by-line verification of load-bearing claims ·
  same-model draft+review with no independent pass
```

## Sources

- [Architecture Decision Records with Codex CLI: Automated ADR Generation, Governance, and the Agent-Architecture Gap](https://codex.danielvaughan.com/2026/04/28/codex-cli-architecture-decision-records-adr-automated-governance/) — the 30-40 minute manual vs minutes-with-AI drafting comparison, continuous ADR-policy-in-AGENTS.md pattern; accessed 2026-08-01
- [Adversarial Code Review: Why the Maker Shouldn't Grade the Checker](https://www.augmentcode.com/guides/adversarial-code-review) — the self-review structural argument, architecture as the weakest review category, the institutional-memory gap; accessed 2026-08-01
- [Cross-Model Adversarial Review: Using Multiple AI Models to Catch Agent Blind Spots](https://codex.danielvaughan.com/2026/03/28/cross-model-adversarial-review/) — cross-model-family review rationale; accessed 2026-08-01
- [Stop Documentation Drift: Tying Technical Docs Directly to Code](https://earezki.com/ai-news/2026-06-13-confluence-docs-lie-tie-your-documentation-to-code-instead/) — the $200K/year figure, 986M-commit 2025 GitHub figure, CI-gated drift detection pattern; accessed 2026-08-01
- `curriculum/28-ai-assisted-architecture/09-claude-architect.md` — the general accountability and Level 1/2/3 enforcement argument this module applies specifically to review artifacts
- `curriculum/27-tooling-debugging/07-reviewing-ai-code.md` — the confidence-carries-no-evidentiary-weight argument for generated code, extended here to generated documentation and design judgment

## Changelog
- 2026-08-01 — created
