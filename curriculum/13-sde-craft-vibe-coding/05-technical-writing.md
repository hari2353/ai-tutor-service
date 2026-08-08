# ADRs, RFCs, Design Docs

> **Track:** T13 SDE Craft & Vibe Coding · **Time:** 1.5h · **Prereqs:** `T13-code-review` · **Updated:** 2026-08-05
> **Module id:** `T13-technical-writing` · **Tags:** craft, writing, staff-signal

## The 30-second version

At staff and principal level the document *is* the work product: a decision that isn't written down didn't happen, and a design that can't survive being read asynchronously by eight people who weren't in the room doesn't scale past one team. Three artifacts, three jobs: an **ADR** is a 1-2 page immutable record of one decision and the forces that produced it, written after the fact and never edited (superseded, not rewritten); an **RFC / design doc** is a mutable pre-implementation proposal that argues among options and seeks consensus, 3-20 pages depending on blast radius; a **spec** is neither, it describes what exists rather than why it was chosen. The highest-leverage section in any of them is **non-goals**, because it's the only section that pre-empts the review comments that would otherwise consume three weeks, and non-goals are things that could reasonably have been goals and were deliberately excluded, not negated goals like "shouldn't be slow." The two failures interviewers actually probe for are documents that assert instead of argue (a decision with no rejected alternatives is an implementation manual, and Google's own guidance says write the code instead) and documents that die in comments because the author defended every objection rather than triaging which ones were blocking.

## Why this gets asked

Because the interviewer has read a design doc that cost their organization a quarter. Either it was so vague that four teams each implemented a different reading of it and the integration failed at the seams, or it was so long that nobody senior actually read it, approval was a rubber stamp, and the security or privacy problem that a real review would have caught surfaced in production. They have also, almost certainly, watched a technically strong engineer get stuck at senior because their designs were correct and unpersuadable: the ideas were right, the doc got 60 comments, the author argued each one on the merits, and six weeks later the effort was quietly deprioritized because the org never converged. That is a writing failure with an engineering-quality veneer, and it's exactly the failure that separates "very good senior engineer" from "staff."

The mechanical reason it shows up in loops: written communication is one of the five signals Will Larson names for staff-plus loops (self-awareness, judgement, collaboration, communication, development), and unlike the other four it's cheap to test directly. Some companies now attach a take-home writing exercise or a "bring a design doc you wrote, redacted" round. Even where they don't, the system design round is a *verbal* design doc and gets graded on the same structure: did you state the goals, did you name what you're explicitly not solving, did you argue an alternative you rejected, did you say what breaks.

---

## Lineage: past → present → future

**What came before.** Big-design-up-front architecture documentation, formalized by the IEEE 1471 / ISO 42010 lineage and by the SEI's *Documenting Software Architectures* (2002), produced 100+ page architecture description documents with formal viewpoints and stakeholder matrices. The specific pain that killed it in practice was not that it was wrong but that it was never read and never updated: Nygard's own framing in 2011 was that most developers have been on at least one project where the specification document was larger in bytes than the total source code, and that such documents are "too large to open, read, or update." A stale 120-page architecture document is worse than no document, because it actively misleads: a new engineer trusts it, builds on a section that stopped being true 18 months ago, and discovers the drift in production. The Agile reaction of 2001-2010 over-corrected into "working software over comprehensive documentation" read as "no documentation," which produced the opposite failure: teams that could not answer "why is it like this" about any decision older than the current headcount, so every architectural question either got blindly accepted or blindly reversed, both of which Nygard called out explicitly as the failure mode ADRs exist to prevent.

**Where it stands now.** Three formats have stabilized and they are complementary, not competing. **ADRs** (Michael Nygard, *Documenting Architecture Decisions*, 15 November 2011) are a 5-part, 1-2 page immutable record: Title, Context, Decision, Status, Consequences, kept in-repo at `doc/arch/adr-NNN.md`, numbered monotonically, never renumbered, superseded rather than deleted. **MADR** (Markdown Any Decision Records, 4.0.0 released 2024-09-17) is the most-used evolution, adding explicit "Considered Options" and "Decision Outcome" fields and shipping four template variants (full, minimal, bare, bare-minimal). **Design docs / RFCs** are the pre-decision artifact: Google's internal form, described publicly by Malte Ubl in *Design Docs at Google* (2020), runs context and scope → goals and non-goals → the actual design → alternatives considered → cross-cutting concerns, with a stated sweet spot of 10-20 pages for a large project and an explicitly blessed 1-3 page "mini design doc." Open-source governance formalized the same shape earlier and more rigorously: Python's PEP process (PEP 1, 2000), Rust's RFC template (motivation, guide-level explanation, reference-level explanation, drawbacks, rationale and alternatives, prior art, unresolved questions, future possibilities), and Kubernetes KEPs, which add the operational sections most corporate templates omit: test plan, graduation criteria, upgrade/downgrade strategy, version skew, and a Production Readiness Review questionnaire. Amazon's 6-pager narrative memo (Bezos banned PowerPoint for S-team reviews in 2004, initially 4 pages, later 6) is the outlier and worth knowing because it inverts the review model: everyone reads in silence for the first 20-25 minutes of the meeting, which structurally solves the "nobody read the doc" failure that comment-thread review does not.

The live disagreements are real and you should be able to name them. First: **should ADRs be mutable?** Nygard's position is no, a superseded ADR stays as written with a pointer forward, because the historical record of what the team believed at the time is the actual value. MADR-in-practice at many shops edits in place, which quietly destroys that value and produces ADRs that all read as if the team was always right. Second: **RFC gate versus RFC advisory.** Squarespace's public write-up on their RFC process describes shifting to a "Yes, if" norm precisely because a blocking-by-default review turned into pile-on and bikeshedding; other orgs (Uber's ERDs, Google's staffed design review meetings) keep a hard gate for anything crossing a team boundary. Third: **how much of this survives AI-assisted development.** The volume of generated code has gone up faster than the volume of considered decisions, and there is an active argument about whether ADRs become *more* valuable as machine-readable context for coding agents or become noise nobody maintains.

**Where it's heading.** Highest confidence: **decision records as agent context** is already happening and will consolidate. `AGENTS.md`, `CLAUDE.md`, and in-repo ADR directories are converging on the same job, giving a code-generating model the "why" it cannot infer from the code, and the MADR project shipping a YAML variant (YADR, March 2026) is a direct signal that machine consumption is now a first-class design constraint on the format. Medium confidence: **the review meeting comes back**, in Amazon's read-in-silence form, because comment-thread review has a measurable convergence problem and synchronous reading is the only intervention that reliably fixes "the four people who mattered skimmed it." Speculative, flag it as such: **model-drafted design docs with human-owned goals and non-goals.** The mechanical sections (context, API sketch, data storage, alternatives-as-a-survey) draft well from a prompt; goals, non-goals, and the honest argument for the rejected option require organizational context and a willingness to be wrong in writing, and those are exactly what a review is grading. Expect the median doc's word count to rise and its information content to fall, which makes a *short* well-argued doc a stronger differentiator in 2026 than it was in 2020.

---

## Mental model

Three artifacts, one axis: **when in the decision's life is it written, and is it allowed to change.**

```
                 BEFORE the decision        AT the decision         AFTER, describing
                 (argue, converge)          (record, freeze)        (what exists now)
                 ─────────────────────      ──────────────────      ─────────────────
  ARTIFACT       RFC / design doc           ADR                     spec / runbook / README
  MUTABLE?       yes, heavily, that's       NO. superseded by       yes, tracks reality
                 the point                  adr-014, never edited
  LENGTH         1-3 pg (mini)              1-2 pages, hard cap     whatever it takes
                 10-20 pg (large)
  ANSWERS        "which option, and why     "why is it like this,   "how do I use / operate
                 not the others?"            and what did we know   this thing today?"
                                             at the time?"
  AUDIENCE       reviewers who can           the engineer in 2029    the engineer on call
                 still change your mind      asking 'what were       at 03:00
                                             they thinking?'
  DIES WHEN      it argues nothing           it gets edited to      it drifts from reality
                 (implementation manual)     look prescient          and nobody notices


THE SHAPE OF A DOC THAT GETS READ  (inverted pyramid, not a mystery novel)

  ┌───────────────────────────────────────────────────────────┐
  │ TL;DR — the decision, in 3 sentences, at the very top     │  ← 100% read this
  ├───────────────────────────────────────────────────────────┤
  │ Context (facts only, value-neutral) + Goals + NON-GOALS   │  ← 80% read this
  ├───────────────────────────────────────────────────────────┤
  │ Decision + the one diagram                                │  ← 60%
  ├───────────────────────────────────────────────────────────┤
  │ Options considered, incl. the ones you rejected, argued   │  ← 30%, but they are
  │ at their strongest                                        │    the ones who matter
  ├───────────────────────────────────────────────────────────┤
  │ Consequences (incl. the bad ones) · Rollout · Open Qs     │  ← 15%
  └───────────────────────────────────────────────────────────┘

  Corollary: if the decision is on page 7, you have written a mystery novel.
  Reviewers do not read mystery novels. They comment on page 2 and leave.
```

The single most useful reframe: **you are not writing to explain, you are writing to be disagreed with efficiently.** A doc's job is to surface the strongest objection as early and as cheaply as possible. That is why non-goals sit near the top (they kill the entire class of "have you considered X" comments before they're typed), why rejected options must be argued at their strongest (a strawman invites a reviewer to rebuild the real version in a comment thread, at 10x the latency), and why "Open questions" is a section and not an admission of weakness (naming your own uncertainty converts a would-be blocking objection into a scoped discussion you framed).

## How it actually works

### The ADR format, exactly as Nygard specified it

Five parts, one decision, one to two pages, stored in the repo the decision governs:

```
doc/arch/adr-007-vector-store-for-rag-retrieval.md

# ADR 7: <short noun phrase, not a sentence>

## Context
   The forces at play: technological, political, social, project-local.
   These forces are IN TENSION and must be called out as such.
   Language here is VALUE-NEUTRAL. Facts only. No advocacy.

## Decision
   "We will ..."  Active voice. Full sentences. One decision.

## Status
   proposed | accepted | deprecated | superseded by ADR-014

## Consequences
   The resulting context after applying the decision.
   ALL of them: positive, negative, neutral. Especially negative.
```

Four constraints in the original that people drop, and each one has a cost when dropped:

1. **Numbered sequentially and monotonically; numbers are never reused.** If ADR-007 is superseded you write ADR-014 and mark 007 `superseded by ADR-014`. You do not delete 007 and you do not renumber. Dropping this costs you the ability to cite a decision durably in a postmortem or a PR description, because the identifier stops being stable.
2. **Superseded, never rewritten.** The value of the archive is that it records what the team believed *at the time*, with the information they had. An ADR corpus that has been edited into consistency reads as if the team was always right, which teaches a new engineer nothing about how decisions actually get made and destroys the one thing you can't reconstruct: the constraint set that no longer exists.
3. **Value-neutral Context.** The Context section describing "Weaviate is bloated and expensive" is advocacy, and it means a reader who disagrees stops trusting the whole document. "Weaviate's managed tier prices per stored vector; at 40M vectors that is $X/month against a $Y/month budget" is a fact, and it does the same argumentative work without spending your credibility.
4. **Prose, not bullets.** Nygard is explicit and unusually blunt: bullets are acceptable for visual style, not as an excuse for sentence fragments. The reason is that fragments let you skip the connective reasoning. "Latency concerns" is a fragment that hides whether you mean p50, p99, ingest, or query, and the reader in 2029 cannot recover which one you meant.

### What an ADR is NOT

This is the highest-value distinction in the module and it is the one candidates get wrong in interviews.

| An ADR is NOT | Why people confuse it | What to write instead |
|---|---|---|
| A design doc | Both discuss options | Design doc *proposes and argues* before consensus; ADR *records* after. A design doc that ends in one decision often yields one ADR as its output |
| A spec | Both describe a system | A spec describes what the system does now and is updated forever; an ADR describes one choice at one moment and is frozen |
| A ticket / epic | Both live near the work | A ticket tracks execution state; an ADR has no state beyond proposed/accepted/superseded and no assignee |
| A postmortem | Both are retrospective | A postmortem explains one incident's causal chain; an ADR explains one decision's forces. An incident may *cause* an ADR |
| A place for implementation detail | It feels like documentation | If it would change when you refactor, it doesn't belong. ADRs record what survives the refactor: the constraint and the choice |
| A record of every decision | "We should document everything" | Only *architecturally significant* ones: things affecting structure, non-functional characteristics, dependencies, interfaces, or construction technique. `black` over `yapf` is not an ADR. Postgres over DynamoDB is |
| A consensus-building tool | Both get circulated | An ADR is a poor consensus tool because its format has nowhere to argue at length. If you need to convince people, write an RFC and *then* the ADR |

The tell that a team has confused ADRs with design docs: their `doc/arch/` directory has eight files, three of them are 4,000 words, and none of them has a Status line that was ever changed after the day it was written.

### The design-doc / RFC structure that actually gets read

```
TL;DR                     3 sentences. The decision and the one number that drives it.
Context and scope         Objective background. Links, not exposition. No advocacy.
Goals                     Bullets. Each one falsifiable or measurable.
Non-goals                 Bullets. Things that could reasonably have been goals.
The design                Overview first, then detail. ONE system-context diagram.
Options considered        Including the rejected ones, argued at their strongest.
Decision                  Which one and the deciding criterion, named explicitly.
Consequences              Including what gets worse. Including what this forecloses.
Rollout                   Phases, the kill switch, the rollback, what you measure.
Open questions            Named uncertainty, with an owner and a date, not a shrug.
Cross-cutting concerns    Security, privacy, cost, observability, on-call load.
```

Three observations about this structure that matter more than the list itself.

**The order is load-bearing.** Goals before design, design before alternatives, alternatives before decision. A reader who hits your design before your goals has no criterion for evaluating it, so they evaluate it against *their* goals, and you get comments that are technically about your design but actually about a goal disagreement you never surfaced. Roughly half of the "this reviewer just doesn't get it" experience is a goals section that was too vague to disagree with.

**"Rollout" is the section that separates staff docs from senior ones.** Kubernetes KEPs make this structural: a KEP is not complete without a test plan, graduation criteria, an upgrade/downgrade strategy, version skew handling, and a Production Readiness Review questionnaire covering feature-gate rollback and monitoring. Most corporate design doc templates stop at "the design," which is why the doc reads as an architecture exercise rather than a plan someone will be on call for. If you write only one section better than your peers, write this one: phases with a measurable gate between them, an explicit rollback path, and the metric that tells you the rollback is needed.

**Length is a decision, not an outcome.** Google's stated sweet spot is 10-20 pages for a large project and an explicitly blessed 1-3 page mini doc for incremental work, "you still do all the same steps, just keep things more terse." Past ~20 pages the correct move is to split the problem, not to keep writing, because the marginal page after 20 is read by approximately nobody and every unread page is a place for an unreviewed mistake to hide.

### Why non-goals is the highest-leverage section

A non-goal is something that **could reasonably have been a goal** and was deliberately excluded. Malte Ubl's canonical example: for a database design, ACID compliance is a legitimate non-goal, stated as such, and you might still pick a solution that provides it if that doesn't cost you the actual goals. What a non-goal is *not*: a negated goal. "The system shouldn't crash" is not a non-goal, it's a goal you forgot to write down, and putting it in the non-goals section is the single most common tell that the author copied the template without understanding it.

The leverage is mechanical, not stylistic. Every reviewer arrives with a mental list of things a system like yours might do. Anything on their list that isn't on your goals list generates a comment: "have you considered multi-region?", "does this handle the 22-locale case?", "what about the batch path?". Each of those costs a round trip of 4 to 48 hours in a comment thread. A non-goals section that names the six most likely such questions and says "not in scope, here's the reason, here's when we'd revisit" converts six threads into zero. On a doc with 12 reviewers that is the difference between converging in three days and converging in three weeks.

The second-order effect matters more. A non-goal is a *commitment*, and reviewers know it: writing "multi-region replication is a non-goal for v1; we accept a 15-minute RPO and will revisit if the EU tenant lands" tells a reader you have thought about the boundary and are willing to be held to it. Writing nothing tells them you haven't thought about it, and a reasonable reviewer's response to "hasn't thought about it" is to make you think about it now, in the comments, at maximum latency.

The failure mode of non-goals, which you should be able to name in an interview: using them to smuggle out the hard part. "Correctness under concurrent writes is a non-goal" is not scoping, it's abdication. The test is whether the non-goal is something a competent reviewer would accept as a legitimate v1 boundary, or something that makes the goals unachievable in practice. If excluding it means the system doesn't actually work, it was never a non-goal.

### Writing for the reviewer who will skim

Assume every reader is (a) senior, (b) reading on a phone between meetings, (c) will give you 90 seconds before deciding whether to read properly or drop a comment and leave. That assumption changes concrete things:

- **Decision in the first 3 sentences.** Not "this document explores options for our vector store." That sentence has zero information. "We will move RAG retrieval from Weaviate to pgvector with HNSW, accepting a p99 regression from 45ms to 70ms in exchange for removing a second datastore from the on-call surface and $N/month." That sentence is the entire document, and a reader who stops there has still received the decision.
- **One diagram, not five.** A system-context diagram showing your thing inside the landscape the reader already knows. Five diagrams means the reader picks the wrong one.
- **Numbers in headings and bullets, not buried in paragraphs.** "Ingest throughput: 12k vectors/sec measured on 3× r6g.2xlarge" scans; "we found ingest performance to be acceptable" does not, and also isn't a claim.
- **No code except novel algorithms.** Google's guidance is explicit: design docs should rarely contain code or pseudo-code, and formal interface/schema definitions should not be pasted in because they are verbose and go stale. Link the prototype instead; "I tried it and it works" with a link is one of the strongest arguments available to you.
- **Tables for anything with three or more options.** A comparison paragraph forces the reader to build the table in their head, and half of them build it wrong.
- **The bad news goes in the doc, not in the meeting.** A Consequences section that lists only upsides is read as marketing and triggers adversarial review. A Consequences section that opens with "this adds a second write path and increases p99 on the ingest side by roughly 20%" buys you the benefit of the doubt on everything else in the document.

### Arguing a rejected option honestly

The rejected-options section is where the interviewer, and the reviewer, actually reads for signal. Three rules:

1. **State the rejected option at its strongest, in its advocate's words.** If someone on the team wants Weaviate, write the Weaviate case the way *they* would write it, then explain what tipped it. If you strawman it, one of two things happens: the advocate rebuilds the real argument in a comment thread (expensive, and now it's adversarial), or nobody objects and you ship having never actually tested the decision.
2. **Name the deciding criterion explicitly, and admit it's a criterion and not a law of nature.** "pgvector wins because it's better" is not an argument. "We weighted operational surface above p99 latency because we have 2 on-call engineers and 8 services; a team with a dedicated platform group would reasonably weight the other way" is an argument, and it is also the sentence that tells a reviewer exactly where to push if they disagree, which is what you want.
3. **Say what would flip the decision.** "If retrieval QPS exceeds ~800 sustained, or the corpus passes 50M vectors, pgvector's index maintenance cost changes the answer and we revisit." This is the highest-signal sentence in most documents. It converts a decision into a falsifiable one, and it is what lets the team in 2028 know whether the decision expired.

Rust's RFC template encodes this discipline in three separate required sections rather than one: **Drawbacks** ("why should we *not* do this"), **Rationale and alternatives** ("why is this design the best in the space of possible designs"), and **Unresolved questions**. Notably, Rust's guidance on Drawbacks asks for what the proposal *forecloses*, what kinds of features become impossible later because this exists, which is a much sharper question than "what are the downsides."

### Getting a doc through review without it dying in comments

The failure is well documented and has a name shape: reviewers unsure what they're supposed to be checking, so they comment on what they *can* evaluate, which is the trivial part everyone understands (Parkinson's law of triviality, the bike shed), and authors experiencing that as a pile-on and responding by defending every thread. The doc then dies not because it was rejected but because it never converged.

The mechanics that actually work:

- **Pre-review the doc with the two people most likely to block it, before it goes wide.** Not for approval, for objection discovery. Both objections you can fix in the doc are worth more than either objection surfaced in a public thread, because in a public thread the objector is now on record.
- **State the review ask at the top.** "I need a decision on the storage choice by Thursday; the API shape and the naming are not what I need feedback on right now." Reviewers comment on what they think you want. Tell them.
- **Adopt "Yes, if" over "No, because."** Squarespace published exactly this shift for their RFC process: reviewers frame objections as conditions for approval rather than rejections. It changes the author's job from defending to satisfying a list, and it forces the objector to name what would actually satisfy them, which reveals the surprising number of objections that have no such condition (those were preferences).
- **Triage comments into three buckets, publicly, in the doc.** Blocking (correctness, security, a named cost that compounds) → address. Non-blocking-but-fix → fix silently. Preference with no stated cost → reply once with "noted, going with the current approach because X," and do not re-litigate. The single biggest cause of a doc dying is an author who treats all three buckets identically.
- **Timebox.** "Comments close Friday; unaddressed non-blocking comments become open questions in the doc and we proceed." A doc without a comment deadline is a doc that is still open in nine months.
- **For anything genuinely contentious, buy the synchronous read.** The Amazon pattern (30 minutes, first 20-25 in silence reading, then discussion) exists because async review has a participation problem: the people whose objections matter most are the busiest and skim hardest. One 30-minute meeting where six senior people demonstrably read the document beats three weeks of comment threads where four of them didn't.

### When a doc is the wrong tool

Google's own guidance draws this line more sharply than most corporate templates do, and being able to state it is a senior signal.

- **When the solution isn't ambiguous.** If there is no real tradeoff, the doc becomes an implementation manual: "this is how we will implement it" with no alternatives, no trade-offs, no decision-making shown. The explicit advice is that if that's what you're writing, write the actual program instead. The document has zero information content and costs a week of reviewer attention.
- **When you're prototyping.** Design-doc overhead is incompatible with rapid iteration, and prototyping is often *how you produce* the design doc, not a substitute for it. "I built it and here's what happened" is stronger evidence than any amount of prose.
- **When the real problem is that two people disagree and haven't talked.** A document is a terrible conflict-resolution device: it makes positions public and therefore harder to abandon. Have the 20-minute conversation, then write the doc that records where you landed.
- **When it's one decision with obvious consequences.** That's an ADR (or a PR description), not a design doc. Writing eight pages for a two-paragraph decision trains your reviewers to skim your future documents.
- **When the decision is reversible and cheap.** A two-way door taken quickly and reversed costs less than the review cycle that would have prevented it. Save the process for one-way doors: data model changes, public API shapes, anything with a migration.
- **When the audience is one person.** Write them a message. A doc is a coordination artifact; its cost scales with the number of readers you're asking to spend attention, and its value does too.

---

## Worked example 1 — a real ADR

Subject: the vector store choice behind the RAG retrieval path. This is written the way it should be written, at the length it should be, in Nygard's five parts. The figures below are illustrative of the shape; **swap in your own measured numbers before this becomes a writing sample**, because the one thing an interviewer will probe is where a number came from.

```markdown
# ADR 11: pgvector with HNSW as the primary retrieval index

## Context

Retrieval for the assistant currently runs against a managed Weaviate cluster
holding 41M chunk embeddings (bge-large-en-v1.5, 1024-dim, cosine). Two forces
are in tension.

Operationally, Weaviate is the eighth datastore in a platform run by an on-call
rotation of 4 engineers. It has its own upgrade cadence, its own backup story,
its own auth model, and its own failure signature; in the last two quarters it
accounted for 3 of 11 retrieval-path pages, none of which were caused by a
retrieval defect. Every incident touching it starts with someone reading the
Weaviate docs for twenty minutes.

Against that, Weaviate's HNSW implementation is measurably faster on our shape
of query: p99 45ms at 120 QPS with ef=128, against 70ms for pgvector 0.8 HNSW
on the same corpus and hardware class, and it gives us hybrid BM25+vector
scoring in one call, which we currently use for 30% of queries.

The corpus is growing roughly 1.5M chunks/month and is not expected to pass
60M within the planning horizon. Retrieval QPS peaks at 120 and has been flat
for two quarters. Recall@20 after the BGE reranker is 0.91 on our eval set and
is dominated by the reranker, not by the ANN stage: dropping ef from 128 to 64
moved end-to-end recall@20 by 0.004.

Politically, the platform team has an explicit objective this half to reduce
the number of independently-operated stateful services. There is no dedicated
platform group; the same 4 engineers own the datastores and the services.

## Decision

We will move primary retrieval to pgvector 0.8 with an HNSW index (m=16,
ef_construction=200, ef_search=100) on the existing Aurora PostgreSQL cluster,
and decommission the Weaviate cluster once dual-read has been clean for 14 days.

Hybrid scoring will be reimplemented as PostgreSQL full-text `ts_rank_cd`
combined with vector distance in a single query, with the fusion weights
re-tuned against the existing eval set before cutover.

## Status

Accepted 2026-05-12. Supersedes ADR 4 (managed Weaviate for retrieval, 2024-11).

## Consequences

Retrieval p99 rises from 45ms to approximately 70ms. Against a 2.4s end-to-end
assistant budget this is 1% of the budget and is not user-visible; it is,
however, a real regression and it constrains any future design that wants to
issue more than one retrieval round trip per turn.

The on-call surface loses one stateful service. Backup, PITR, IAM, and
observability collapse onto the Postgres story the team already knows. We
expect this to be the dominant benefit and it is the reason for the decision.

We lose Weaviate's built-in hybrid scoring and take on the maintenance of our
own fusion. Initial implementation cost is estimated at 1 engineer-week plus
re-tuning; ongoing cost is that the fusion weights are now our problem when
the embedding model changes.

Index build time goes from Weaviate's incremental behaviour to a ~50 minute
HNSW build on 41M rows, which means a full reindex is now a scheduled
operation rather than a background one. Embedding-model migrations get more
expensive.

We become exposed to pgvector's index-maintenance behaviour under write load.
At the current 1.5M chunks/month ingest this is not a concern; at roughly 5x
that rate, or beyond ~60M vectors, we expect to revisit this decision.

We foreclose, for now, any retrieval feature that depends on Weaviate-specific
capability (multi-tenancy per class, its module ecosystem). Nothing on the
current roadmap depends on those.
```

Read what that document is doing. The Context section contains no advocacy: "Weaviate is the eighth datastore" and "3 of 11 retrieval-path pages" are facts, and the reader who loves Weaviate can still trust them. The tension is stated explicitly in both directions, including the fact that the option being rejected is *faster*. The Consequences section leads with the regression. And the last three paragraphs each name a boundary condition (60M vectors, 5x ingest, roadmap dependency on Weaviate modules) that tells a future reader whether the decision has expired. That last property is what makes an ADR worth keeping.

What it deliberately does **not** contain: the migration plan, the dual-read mechanics, the SQL, the eval methodology. Those go in the design doc or the tickets. An ADR that grows a rollout plan has become a design doc and will stop being read.

---

## Worked example 2 — an abbreviated design doc

Same problem class, different artifact: the Java→Python service migration. This is the 1-3 page "mini design doc" form, showing the full structure at terse length. Note how much work the Non-goals section does.

```markdown
# Migrating the scoring service from Java/Spring to Python

Status: in review · Author: HD · Reviewers: <platform, ML, on-call leads>
Decision needed by: 2026-06-05 · Comments close: 2026-06-03

## TL;DR

We will port the scoring service from Java 17/Spring Boot to Python 3.12 +
FastAPI over three phases behind a traffic-split, accepting a projected p99
increase of 8-12ms in exchange for collapsing two model-serving codepaths into
one and removing the JVM from the ML team's iteration loop. Rollback is a
config flag at every phase; no data migration is involved.

## Context and scope

The scoring service ranks candidates for 8 downstream recommendation surfaces.
It is one of two places in the platform where a model is evaluated in a request
path; the other (the feature enrichment service) is already Python. Model
authors are ML engineers who work in Python and currently hand off to a
Java-owning team for productionisation, a handoff that has averaged 9 days
across the last 6 model updates.

The service is stateless. Traffic is 900 RPS peak, p99 currently 34ms, SLO 60ms.
It reads features from Redis and a feature-store table; it writes nothing.

Out of scope for this doc: the feature store itself, the offline training
pipeline, and the recommendation API contract, none of which change.

## Goals

- Model authors can ship a scoring model change without a cross-team handoff.
  Measured: median model-update lead time under 2 days, from 9.
- One model-serving codepath across the platform, not two.
- p99 stays under the 60ms SLO at 900 RPS with headroom for 2x.
- Zero-downtime migration with per-phase rollback in under 5 minutes.

## Non-goals

- **Improving model quality.** This is a port. Any scoring output difference
  beyond float tolerance is a bug, not an improvement, and blocks the phase.
- **Reducing latency.** We expect to be slower. We are buying iteration speed
  with a latency budget we currently have spare (34ms against a 60ms SLO).
- **Migrating the other 7 services off the JVM.** This one has a specific,
  measured handoff cost. The others do not, and nothing here should be read as
  a platform-wide direction.
- **Rewriting the feature-fetch layer.** Tempting during a port, and it would
  make the output-equivalence check impossible to run. Separate doc, later.
- **Multi-model serving / A-B in the service.** The traffic layer already does
  this. Adding it here duplicates a working mechanism.

## The design

  clients ──▶ [ traffic split, config-driven % ] ──┬──▶ scoring-java (Spring)
                                                   └──▶ scoring-py (FastAPI)
                        both ──▶ Redis (features) ──▶ feature-store table

Both implementations run concurrently behind a percentage split held in config.
The Python service reuses the existing feature-fetch contract byte-for-byte.
Model artefacts are loaded from the same S3 prefix; the Java path deserialises
via its existing loader, the Python path via the ML team's existing loader,
already used in the feature enrichment service.

A shadow comparator samples 1% of requests, runs both paths, and emits a
per-request score delta to the metrics pipeline. Phase gates are defined
against that delta, not against latency.

## Options considered

**A. Port to Python/FastAPI behind a traffic split.** (Chosen.) Highest
confidence in output equivalence because both paths run against live traffic
and are compared per-request. Cost: two services in production for ~6 weeks
and the operational awkwardness that implies.

**B. Keep Java, expose a model-loading plugin API so ML authors ship artefacts
without touching Java.** This is the strongest alternative and it was argued
for on the grounds that it preserves the latency profile and avoids a rewrite
entirely. It fails on the actual goal: the 9-day handoff is not caused by the
model artefact, it is caused by the surrounding scoring logic changing with
almost every model update (new features, changed normalisation), which a
plugin API does not address. If the handoff were purely artefact shipping,
B would be the correct choice and this doc would not exist.

**C. GraalVM native-image the Java service and leave the handoff alone.**
Solves a problem we do not have (startup time) at meaningful build complexity.
Rejected in one line because nobody argued for it.

**D. Big-bang cutover, no traffic split.** Two weeks faster and removes the
dual-run awkwardness. Rejected because we have no way to establish output
equivalence at 900 RPS without running both, and a silent scoring regression
on a recommendation surface is the class of bug that is discovered in a
business metric review three weeks later, not in an alert.

## Decision

Option A. The deciding criterion is **verifiability of output equivalence**,
weighted above migration duration and above latency. A team with a strong
offline replay harness could reasonably weight this differently and choose D.

## Consequences

- p99 rises an estimated 8-12ms (measured on a 5% canary before phase 2).
- Two services in production for ~6 weeks; on-call runbook covers both, and
  the split config is the first thing to check in any scoring-path incident.
- JVM expertise stops being required for scoring changes, and stops being
  maintained. If we need it back in 18 months it will be expensive.
- The shadow comparator is throwaway code we will actually have to throw away;
  add a deletion ticket to phase 3 or it lives forever.

## Rollout

Phase 1 (week 1-2): 1% shadow traffic, no production reads from Python.
  Gate: |score delta| < 1e-6 on 99.9% of sampled requests over 72h.
Phase 2 (week 3-4): 5% → 25% live. Gate: p99 < 50ms, error rate within
  0.01% of Java path, no scoring-attributable regression in surface CTR.
Phase 3 (week 5-6): 50% → 100%, Java path idle but deployed for 14 days.
  Gate: 14 clean days, then decommission and delete the comparator.
Rollback at any phase: set split to 0% (config push, ~90 seconds). No data
  migration, no schema change, so rollback is genuinely free.

## Open questions

1. Do we need the comparator at phase 3, or is 1% shadow at phase 1 enough
   evidence? (Owner: HD. Resolve before phase 2.)
2. Does the Python path's GC behaviour hold at 2x traffic, or do we need to
   pin worker counts? (Owner: platform. Load test scheduled week 2.)
3. Who owns scoring on-call after the JVM path is gone? (Owner: eng managers.
   Blocking for phase 3, not for phase 1.)

## Cross-cutting

Security: no new external surface, same IAM role, same VPC. No PII in scoring
inputs beyond the already-classified feature vector.
Cost: +1 service's worth of compute for 6 weeks (~$Xk), then net neutral.
Observability: the Python path must emit the same 6 metrics with the same
names before phase 2, or dashboards and alerts silently go blind on cutover.
```

Three things to notice, because they are what a reviewer grades.

**Option B is argued at its strongest and then defeated on evidence, not on taste.** The doc concedes explicitly that if the handoff cost were purely artefact shipping, B would win and the document would not exist. That single sentence does more to make the decision credible than three paragraphs of advocacy would, and it also tells any reviewer holding the B position exactly which fact to attack (the claim about *why* the 9 days happen), which is a much faster conversation than attacking the conclusion.

**The non-goals kill the six most likely comment threads.** "Improving model quality," "reducing latency," "migrate everything off the JVM," and "rewrite feature-fetch" are each a comment somebody was going to leave. Pre-empting them costs 40 words and saves a week.

**The gates are numeric and the rollback is timed.** "|score delta| < 1e-6 on 99.9% of sampled requests over 72h" is a gate. "Once we're confident" is not a gate, it is a place where a schedule goes to die.

---

## Practical exercise

Write one ADR, for a decision you actually made, and grade it against the rubric. Budget 45 minutes for the draft and 15 for the self-grade. Do not skip the self-grade; the rubric is where the learning is.

**Pick one:**

- **A.** The vector store choice: Weaviate vs pgvector vs ClickHouse HNSW for RAG retrieval. Good choice if you want to practise the three-way comparison and the "deciding criterion" sentence, because all three are defensible and the answer genuinely depends on weights you have to state.
- **B.** The Java→Python migration for the scoring service. Good choice if you want to practise consequences, because a migration's consequences are mostly negative and writing them honestly is the hard part.
- **C.** Any decision from the 8-service recommendation platform where you can still remember what you *didn't* know at the time. That last property is the one that makes an ADR worth writing.

**Constraints, enforced:**

1. **Maximum 800 words.** Hard cap. Over 800 and you have written a design doc.
2. **Nygard's five sections only.** Title, Context, Decision, Status, Consequences. No "Background," no "Appendix," no "Implementation plan."
3. **Context contains zero advocacy.** Read it back and delete every evaluative adjective. "Bloated," "clunky," "modern," "elegant," "clean" all come out. If deleting the adjective destroys the sentence, the sentence was an opinion wearing a fact's clothes.
4. **At least 5 real numbers**, from measurement or from a system of record, not from memory-plus-rounding. If you don't have the number, write `[measured: TBD]` rather than inventing one, and note that you'd block the ADR on getting it.
5. **At least one boundary condition** in Consequences: the threshold at which this decision expires.
6. **One rejected option must appear in Context as a force, in the words of someone who wanted it.** ADRs don't have an "alternatives" section; the alternatives live inside Context as forces in tension. This is the part everyone gets wrong.

**Rubric — score yourself 0/1/2 on each. 18 is the bar for a writing sample you'd hand an interviewer.**

| # | Criterion | 0 | 1 | 2 |
|---|---|---|---|---|
| 1 | **Title is a noun phrase naming the decision** | A sentence, or a ticket number, or "Vector DB investigation" | Noun phrase but vague ("Storage changes") | "pgvector with HNSW as the primary retrieval index" |
| 2 | **Context is value-neutral** | Contains advocacy or evaluative adjectives | One or two slip through | Zero. A reader who disagrees with the decision would still sign off on every sentence in Context |
| 3 | **Forces are shown in tension** | Only the forces supporting the decision appear | Opposing force mentioned but not weighted | The strongest argument *against* the decision appears in Context, stated fairly, including where the rejected option is objectively better |
| 4 | **Numbers are real and sourced** | Adjectives ("fast," "expensive") | Numbers present but unattributed | ≥5 numbers, each traceable to a measurement, a bill, or a system of record; unknowns marked TBD rather than guessed |
| 5 | **Decision is one decision, active voice, "We will..."** | Multiple decisions bundled, or passive/hedged | One decision but hedged ("we should probably") | One decision, active, unhedged, with the specific parameters (index type, m, ef) that make it actionable |
| 6 | **Status is meaningful** | Missing, or "done" | Present | Present with a date, and if it supersedes something, the ADR number it supersedes |
| 7 | **Consequences include the bad ones first** | Only upside | Downsides present but buried or softened | The regression or added cost is stated before the benefits, with a number |
| 8 | **A boundary condition is named** | Absent | Vague ("if scale increases") | Specific and checkable ("beyond ~60M vectors or 5x current ingest rate") |
| 9 | **Foreclosure is named** | Absent | "This limits future flexibility" | What specifically becomes impossible or expensive later, and whether anything on the roadmap needs it |
| 10 | **Length and form** | Over 800 words, or bullet fragments instead of prose | Within cap but choppy | Under 800 words, full sentences, readable end to end in under 4 minutes |

**Then do the harder second pass**, which is the one that maps directly to the interview:

- Hand it to someone who was *not* in the decision and ask them one question: **"what would have to be different for us to have chosen the other option?"** If they can answer from the document alone, the ADR works. If they can't, your Context is missing a force.
- Re-read your own Context and ask whether you'd be comfortable if the person who advocated for the rejected option read it. If the answer is "well, they'd probably object to how I characterised..." then you have not passed criterion 3, regardless of what you scored yourself.
- Time yourself explaining the decision out loud from the doc in 90 seconds. If you have to reach for context that isn't in the document, add it. That 90-second explanation is also, almost verbatim, the answer to "walk me through a design decision you made" in the interview.

**Extension, 30 minutes:** take the same decision and write the *design doc* version, then note what moved. Everything that moved into the design doc (the rollout, the migration mechanics, the eval methodology, the option comparison table) is what does not belong in an ADR. Doing this once is the fastest way to stop confusing the two artifacts, which is the single most common mistake in the interview answer.

---

## How it's done in production

The tooling layer is thin and that's deliberate. **`adr-tools`** (shell, Nygard-format) scaffolds and manages numbering and supersession. **MADR** (4.0.0, 2024-09-17) ships four template variants and is the most common corporate default; **ADR Manager** is a VS Code plugin for section-structured editing; **Log4brains** renders an ADR directory as a static site. Most large orgs, though, run a Google Docs (or Notion/Confluence) workflow for design docs plus in-repo Markdown ADRs, precisely because the two artifacts have different review needs: a design doc needs threaded comments and suggestion mode, an ADR needs to be diffable, greppable and adjacent to the code it governs. Uber calls its design doc an ERD (Engineering Review Doc, formerly RFC), Squarespace and Casper call theirs RFCs, Google calls it a design doc, Amazon uses the 6-pager and the PR/FAQ, and Kubernetes uses the KEP with a mandatory Production Readiness Review. The names differ; the sections don't.

The 2026 wrinkle worth knowing: in-repo ADRs are increasingly consumed by coding agents alongside `AGENTS.md` / `CLAUDE.md`, because they carry the "why" that the code cannot express. MADR shipping a YAML variant (YADR, March 2026) is the format explicitly acknowledging machine consumption. The practical implication is that ADR hygiene (stable numbering, accurate Status, superseded-not-deleted) now has a second consumer that is much less able than a human to infer that a document is stale.

| Symptom | Cause | Fix |
|---|---|---|
| A design doc gets 60+ comments and 4 weeks later has no decision | No stated review ask, no comment deadline, author defending every thread including preference-only ones | State the ask and the close date at the top; triage comments into blocking / fix-silently / preference-with-no-cost and reply once to the third bucket; adopt "Yes, if" framing so objectors must name a satisfying condition |
| All comments are on naming, formatting, and the diagram; nobody engaged with the storage decision | Bikeshedding (Parkinson's law of triviality): reviewers comment on the part they can evaluate in 90 seconds | Put the actual decision and its one deciding number in the first 3 sentences; explicitly say which sections are not open for feedback this round; pre-review with the two most likely blockers before going wide |
| Approvals arrive within 20 minutes of sending a 15-page doc | Nobody read it; the approval is social, not technical | Switch to a synchronous read-in-silence review (Amazon pattern, 20-25 min) for anything contentious; or split the doc, because >20 pages is a signal to split the problem |
| An `doc/arch/` directory where no Status line has ever changed | ADRs are being treated as documentation, not as decision records; decisions get made and the old ADR is silently edited or ignored | Enforce supersede-don't-edit in review; a PR that reverses an architectural decision must add a new ADR and flip the old one's Status, same as a schema change requires a migration |
| A new engineer asks "why is it like this" and nobody, including the author, can answer | The decision predates the ADR practice, or the ADR recorded the *what* and not the *forces* | Write the ADR retroactively while someone still remembers, and mark it clearly as reconstructed; a reconstructed ADR with a caveat beats no ADR, and it is the only version you'll ever get |
| Two teams build to different readings of the same approved design | Goals were written but non-goals were not, so each team filled the gap with its own assumptions | Non-goals section, named explicitly; the ambiguity that produced the divergence is almost always a scope question the doc never answered |
| The design doc is 12 pages of implementation detail with no alternatives section | Author wrote an implementation manual; there was no real ambiguity to resolve | Google's own guidance: if there were no trade-offs, write the program instead. Kill the doc, ship the code, write a 1-page ADR if a decision was actually made |
| Doc approved, project ships, and the doc no longer describes the system | Nobody updated it during implementation, which is the normal human outcome | If it hasn't shipped, update it. If it has, write an amendment doc and link it from the original rather than pretending the original was always right; Google's own practice drifts toward "constitution plus amendments" and links are what make that navigable |
| Reviewer asks "why not X?" about the option you rejected, three separate times, from three people | X was strawmanned or omitted; readers reconstruct the real version themselves | Argue X at its strongest in its advocate's words and name the deciding criterion; three independent people asking is evidence your rejection wasn't argued, not that they didn't read |
| The rollout section says "deploy to production" | The doc is an architecture exercise, not a plan someone will be on call for | Steal the KEP structure: phases with numeric gates, upgrade/downgrade strategy, feature-gate rollback, and the specific metric that signals rollback is needed |

## Tradeoffs & when NOT to use it

The "when a doc is the wrong tool" list above covers the per-document decision. These are the *organizational* tradeoffs, which is where the senior signal actually lives.

- **A mandated RFC gate on every cross-team change buys consistency and pays in latency, and the exchange rate is worse than it looks.** A 5-business-day review SLA on a change that takes 2 days to build has tripled its cost. Squarespace's public account of moving to "Yes, if" is an admission that their first version of the gate was net-negative. The defensible position: gate one-way doors (data model, public API, anything with a migration), advise on two-way doors, and be explicit in writing about which is which. An org that can't tell you which of its RFCs are gates and which are FYIs has a process that will be routed around within two quarters.
- **ADRs have a maintenance floor and below a certain team size you will not clear it.** A 4-person team that writes 3 ADRs and then stops has produced something worse than nothing: a directory that looks authoritative and is 80% stale. If you can't commit to the review-time discipline of flipping Status when a decision is reversed, don't start; a `DECISIONS.md` append-only file with dated one-paragraph entries is genuinely better than an abandoned ADR practice.
- **Writing everything down has a real political cost that nobody mentions.** A document makes a position public, attributable and durable. In an org where being wrong in writing is punished, the rational response is to write documents that assert nothing falsifiable, which is exactly the vague, unarguable doc everyone complains about. If you are joining a team whose design docs have no "Drawbacks" section and no named boundary conditions, that is usually a culture signal, not a template problem, and no amount of template improvement will fix it.
- **Non-goals can be weaponised.** Used honestly they scope; used dishonestly they let an author declare the hard part out of scope and ship the easy part. The test: would a competent reviewer accept this as a legitimate v1 boundary, or does excluding it mean the system doesn't work? Reviewers should read the non-goals section adversarially, and authors should expect them to.
- **The rejected-options section is where docs get padded.** Listing eight alternatives you never seriously considered is not thoroughness, it is noise, and it dilutes the two that actually competed. Three options is usually the right number: the chosen one, the strongest rival, and the obvious-but-wrong one that a reader will otherwise ask about. Rejecting an option in one sentence because nobody argued for it (Option C in the worked example) is correct and honest.
- **Don't write the doc to win the argument you already had.** A design doc written after the decision was politically settled, purely to create a paper trail, is detectable in about 90 seconds: the alternatives are thin, the deciding criterion is post-hoc, and the consequences are all positive. Reviewers who detect it stop reading your documents carefully, permanently. If the decision is genuinely already made, write an ADR (which is honest about being a record) rather than an RFC (which is a lie about seeking input).
- **The 10-20 page sweet spot is for a large project, and most projects aren't large.** The reflex to write to the length of the template rather than the size of the problem is the most common way good engineers waste a week. A one-page doc that names the decision, the rival, the deciding criterion and the rollback is a complete document.

---

## Interview questions

### Q1 — What's the difference between an ADR and a design doc, and when would you write one but not the other?
**Testing:** whether you actually use both, or have read about one and are pattern-matching. This is the warmup and it eliminates a surprising number of people.
**Answer:** An ADR is a 1-2 page immutable record of one decision, written at or after the decision, in Nygard's five sections (Title, Context, Decision, Status, Consequences), kept in the repo, numbered monotonically, superseded rather than edited. A design doc is a mutable pre-decision proposal that argues among options to build consensus, typically 1-3 pages for incremental work and 10-20 for a large project. I write only an ADR when the decision is clear and the value is the durable record: "we chose Aurora over DynamoDB for this service and here's the constraint set." I write a design doc when the solution is genuinely ambiguous and I need reviewers to change my mind. A large design doc often *produces* two or three ADRs as output.
**Follow-up trap:** *"So an ADR is just a short design doc?"* No, and the difference is mutability and audience. The design doc's reader can still change the outcome; the ADR's reader is an engineer in 2029 asking "what were they thinking." That's why an ADR is frozen: the value is a faithful record of what the team believed with the information it had. A team that edits ADRs to stay current has produced a corpus in which they were always right, which teaches nobody anything and quietly destroys the only artifact that captures constraints which no longer exist.

### Q2 — Walk me through a design doc you wrote. What was the decision and what did the doc change?
**Testing:** whether the doc was real and whether review actually moved you. The second half is the whole question.
**Answer:** Structure it as: the decision in one sentence, the goals in one, the non-goals in one, the strongest rival option, the deciding criterion, and then the thing that changed because of review. For the scoring service migration: the decision was to port Java/Spring to Python/FastAPI behind a traffic split; the deciding criterion was verifiability of output equivalence, weighted above migration duration; and review changed the design, because a reviewer pointed out that a big-bang cutover would be two weeks faster and I could not defend the split until I could state what specifically we'd fail to detect without it, which forced the shadow comparator and the numeric phase gate into the doc.
**Follow-up trap:** *"What did you get wrong?"* Have a real answer, and make it a doc failure rather than a technical one. "The first version had goals but no non-goals, so I got four separate comments asking whether this meant we were migrating everything off the JVM, which was never the intent. I added a non-goals section and those threads stopped." A candidate who says the doc was fine and review just confirmed it has told the interviewer the doc was either uncontroversial (so why write it) or unread.

### Q3 — What goes in a non-goals section, and why do you consider it the highest-leverage part of the document?
**Testing:** the single most reliable discriminator between people who use the template and people who copied it.
**Answer:** A non-goal is something that could reasonably have been a goal and was deliberately excluded, with the reason and ideally the condition under which you'd revisit. Malte Ubl's canonical example is ACID compliance for a database design: a legitimate non-goal, and you might still pick something that provides it if it costs you nothing. It's the highest-leverage section for a mechanical reason: every reviewer arrives with a list of things a system like yours might do, and anything on their list not on your goals list becomes a comment thread costing 4 to 48 hours of round trip. Naming the six most likely such items converts six threads into zero. On a doc with 12 reviewers that's the difference between converging in three days and three weeks.
**Follow-up trap:** *"Give me a bad non-goal."* Two kinds. "The system shouldn't crash" is a negated goal, not a non-goal, and it's the tell that someone filled in the template without understanding it. Worse: "correctness under concurrent writes is a non-goal," which isn't scoping, it's declaring the hard part out of scope to ship the easy part. The test is whether a competent reviewer would accept it as a legitimate v1 boundary or whether excluding it means the system doesn't actually work.

### Q4 — You're proposing option A and a respected colleague strongly prefers option B. How do you write the alternatives section?
**Testing:** intellectual honesty under pressure, which is the trait the whole document format exists to test.
**Answer:** Write B at its strongest, in B's advocate's words, ideally after asking them to review that paragraph specifically. Then name the deciding criterion explicitly and admit it's a criterion, not a law: "we weighted operational surface above p99 latency because we have 4 on-call engineers and 8 services; a team with a dedicated platform group would reasonably weight the other way." Then say what would flip it: "if sustained retrieval QPS passes ~800 or the corpus passes 60M vectors, the answer changes." That last sentence is the highest-signal line in most documents because it makes the decision falsifiable and tells the team in 2028 whether it has expired.
**Follow-up trap:** *"Isn't stating the case for B this strongly just undermining your own proposal?"* The opposite. If you strawman B, one of two things happens: the advocate rebuilds the real B in a comment thread, which is 10x the latency and now adversarial, or nobody objects and you ship having never actually tested the decision. Stating B fairly and beating it anyway is the only version where the approval means anything. It also tells reviewers exactly where to push if they disagree, which is a much faster conversation than attacking your conclusion.

### Q5 — Your design doc has 60 comments and no decision after three weeks. What did you do wrong and what do you do now?
**Testing:** whether you've actually shipped a document through a real org, and whether you understand that a doc can fail by not converging rather than by being rejected.
**Answer:** Diagnose first. Most likely causes: no stated review ask so reviewers commented on whatever they could evaluate; no comment deadline; the decision was on page 7 so people commented on page 2 and left; and me defending every thread including preference-only ones. What I do now: triage every open comment into three buckets in the doc itself, publicly. Blocking (correctness, security, a cost that compounds) → address. Non-blocking-but-worth-fixing → fix silently. Preference with no stated cost → reply once with "noted, going with the current approach because X" and stop. Then set a close date, and for the two or three genuinely contentious items, buy 30 minutes of synchronous time with the four people who matter rather than another two weeks of async.
**Follow-up trap:** *"How do you tell a real objection from a preference?"* Does it name a specific cost and the condition under which that cost manifests. "This couples the ingest path to the query path, so next quarter's reindex has to touch both" is an objection. "I'd have used a different pattern" is a preference. The useful forcing function is the "Yes, if" framing Squarespace adopted: ask the objector what would satisfy them. A surprising number of objections have no such condition, and asking reveals it without anyone having to lose an argument.

### Q6 — When would you not write a design doc?
**Testing:** whether process is something you apply or something you reason about. Candidates who can't answer this get read as process-cargo-cult.
**Answer:** Five cases. When the solution isn't ambiguous, because then the doc is an implementation manual and Google's own guidance is to write the program instead. When I'm prototyping, because doc overhead is incompatible with iteration and the prototype is often *how* you produce the doc; "I tried it and it works" with a link is among the strongest arguments available. When the real problem is two people disagreeing who haven't talked, because a doc makes positions public and therefore harder to abandon. When it's one decision with obvious consequences, which is an ADR or a PR description. And when the decision is a cheap two-way door, where taking it and reversing it costs less than the review cycle that would have prevented it.
**Follow-up trap:** *"Your VP mandates a design doc for every project over two weeks. Now what?"* Comply, and write the one-page version, because the mandate is usually a reaction to a real failure (a project that shipped without cross-cutting review). Then attack the actual problem with data rather than by arguing about the mandate: track how many of those docs contain an alternatives section with a genuine rejected option. If it's under half, the mandate is producing implementation manuals and you have an evidence-based case for gating one-way doors only and advising on the rest.

### Q7 — What makes an ADR's Context section good, and what's the most common way it goes bad?
**Testing:** close reading of the format, and whether you understand *why* Nygard specified value-neutral language.
**Answer:** Good Context states the forces at play (technological, political, social, project-local), explicitly acknowledges that they're in tension, and uses value-neutral language: facts only, no advocacy. It includes the forces that argue *against* the decision, including where the rejected option is objectively better. The most common failure is advocacy leaking in: "Weaviate is bloated and expensive" is an opinion, and the moment a reader who disagrees hits it, they stop trusting the entire document including the parts that are facts. "Weaviate's managed tier prices per stored vector; at 41M vectors that's $X/month against a $Y/month budget" does the identical argumentative work without spending credibility.
**Follow-up trap:** *"Where do the alternatives go in an ADR, then? There's no alternatives section."* They go in Context, as forces. That's the part everyone gets wrong. An ADR doesn't have a comparison table because it isn't arguing, it's recording; the rival option appears as a force in tension ("Weaviate's HNSW is measurably faster on our query shape: p99 45ms against 70ms") and the Decision explains what outweighed it. If you find yourself needing a full alternatives section with a table, you're writing a design doc and should stop pretending otherwise.

### Q8 — What sections do most corporate design doc templates omit, and why does it matter?
**Testing:** whether you've read real templates from systems that have to survive operationally, rather than one company's internal wiki page.
**Answer:** Rollout and operational sections. Kubernetes KEPs require a test plan, graduation criteria, an upgrade/downgrade strategy, version skew handling, and a Production Readiness Review questionnaire covering feature-gate rollback and monitoring. Rust's RFC template requires Drawbacks, Rationale and alternatives, Prior art, Unresolved questions, and Future possibilities as *separate* required sections. Most corporate templates stop at "the design," which is why those docs read as architecture exercises rather than plans someone will be on call for. If I improve one section relative to my peers, it's rollout: numbered phases, a numeric gate between each, an explicit rollback path, and the specific metric that says rollback is needed.
**Follow-up trap:** *"Isn't rollout an implementation detail that belongs in a ticket?"* No, because rollout is where the design's risk actually lives and it frequently changes the design. In the scoring migration, the requirement to verify output equivalence at 900 RPS is what forced the traffic split and the shadow comparator into the architecture. If rollout had been deferred to tickets, we'd have designed a big-bang cutover and discovered the verification problem two weeks in. Rollout constraints are design constraints.

### Q9 — Rust's RFC template asks "what does this proposal foreclose?" under Drawbacks. Why is that a sharper question than "what are the downsides?"
**Testing:** whether you can reason about the format itself rather than just fill it in. This is a staff-level question and most candidates have never thought about it.
**Answer:** "Downsides" invites a list of costs you pay now, which are visible, bounded, and usually already priced into the decision. "What does this foreclose" asks about optionality you're destroying, which is invisible at decision time and unbounded. Concretely, for the scoring migration: the downside is +8-12ms p99, which is a number and we accepted it. The foreclosure is that JVM expertise stops being required for scoring changes and therefore stops being maintained, so if we need it back in 18 months it's expensive to reacquire. Nobody would have written that under "downsides" because it isn't a cost today. It's the one that actually hurts.
**Follow-up trap:** *"Give me a foreclosure from your RAG work."* Something like: standardising on a 1024-dim embedding model and building the index around it forecloses cheap experimentation with larger models, because a dimension change means a full ~50-minute HNSW rebuild on 41M rows plus a re-tune of the hybrid fusion weights, which turns "try a new embedding model" from an afternoon into a scheduled operation. The point is that the foreclosure is about the *next* decision's cost, not this one's.

### Q10 — Amazon replaced slide decks with 6-page narrative memos read in silence at the start of the meeting. What problem does that solve that comment-thread review doesn't?
**Testing:** whether you understand review as a mechanism with failure modes, not as a ritual. Also whether you can steal a good idea from a format you don't use.
**Answer:** It solves the participation problem. Async review has a structural flaw: the reviewers whose objections matter most are the busiest and skim hardest, so a 15-page doc can get approvals in 20 minutes that are social rather than technical. Twenty-five minutes of enforced synchronous reading guarantees the six people who matter actually read it, once, at the same time, before anyone anchors the discussion. The secondary effect Bezos was after in 2004 is on the author side: narrative prose forces the connective reasoning that bullets let you skip, which is the same reason Nygard insists ADRs use full sentences rather than fragments.
**Follow-up trap:** *"So should everything be a 6-pager?"* No, the cost is real: it's 25 minutes times the number of attendees, so a 6-person review is 2.5 person-hours before discussion starts. Reserve it for genuinely contentious one-way doors where async has already failed to converge, or where you need to *know* people read it. For everything else async comment review with a stated ask and a close date is cheaper and works fine.

### Q11 — You inherit an eight-service platform where nobody can explain why any architectural decision was made. What do you actually do?
**Testing:** judgement about where documentation effort pays, versus a reflex to document everything. The wrong answer here is "I'd write ADRs for everything," and a lot of people give it.
**Answer:** Don't backfill the archive. Backfill selectively, driven by pain: write a retroactive ADR for a decision only when someone is actively about to change it or is blocked by not understanding it, and mark it clearly as reconstructed so the record is honest about being a reconstruction. That gives you documents with a known reader, which is the only kind that stays accurate. Then set the forward-going rule at review time: any PR that reverses or supersedes an architectural decision must add an ADR and flip the old one's Status, the same way a schema change requires a migration. Enforcement at review is the entire practice; the template is trivial.
**Follow-up trap:** *"Your team writes three ADRs and then stops. Is that better or worse than none?"* Worse. A directory that looks authoritative and is 80% stale actively misleads new engineers, who trust it and build on something that stopped being true. If the team can't commit to flipping Status at review time, an append-only dated `DECISIONS.md` with one-paragraph entries is genuinely better, because its format doesn't promise currency. Knowing when *not* to adopt a practice is the point.

### Q12 — How does heavy AI-assisted code generation change what you write down, if at all?
**Testing:** current-context judgement, and whether you'll make an unhedged claim about a fast-moving thing. The trap is baked in.
**Answer:** Two effects with different confidence. High confidence: decision records become a second consumer's input. In-repo ADRs sit alongside `AGENTS.md` / `CLAUDE.md` and carry the "why" a model cannot infer from code, and MADR shipping a YAML variant (YADR, March 2026) is the format explicitly acknowledging machine consumption. That raises the value of hygiene specifically, stable numbering, accurate Status, superseded-not-deleted, because an agent is much worse than a human at inferring that a document is stale. Lower confidence, and I'd flag it as a hypothesis: the mechanical sections of a design doc (context, API sketch, alternatives-as-a-survey) draft well from a prompt, while goals, non-goals and the honest argument for the rejected option require organizational context and a willingness to be wrong in writing. If that holds, the median doc gets longer and less informative, which makes a short, well-argued one a *stronger* differentiator than it was in 2020.
**Follow-up trap:** *"So design docs are less necessary now that code is cheap to produce?"* Push back on the premise. Cheap code makes the decision *more* important, not less, because the constraint moves from implementation cost to the cost of having built the wrong thing quickly and at volume. The specific thing that got cheaper is producing an implementation; the thing that didn't is knowing which one to produce, and that's exactly what the doc is for. A candidate who agrees enthusiastically that documents matter less in 2026 has said something the interviewer will remember, and not well.

---

## Red flags that fail you

- Using "ADR," "RFC," and "design doc" interchangeably, or describing an ADR as "a short design doc."
- Not knowing what a non-goal is, or giving "the system shouldn't crash" as an example (that's a negated goal).
- Describing a design doc with no alternatives section, or listing alternatives you never seriously considered as evidence of rigour.
- Strawmanning the rejected option, especially when the interviewer is visibly the kind of engineer who would have argued for it.
- No answer to "what would flip this decision," which means you shipped an unfalsifiable claim.
- A Consequences or Drawbacks section with only upside. Read as marketing, triggers adversarial review, and in an interview reads as an inability to hold two things at once.
- Saying you'd write ADRs for every decision, or backfill the whole archive on joining a legacy system.
- Editing an ADR in place when the decision is reversed, and not knowing why supersession exists.
- Treating every review comment as requiring a defense, with no triage between blocking, fix-silently, and preference.
- Claiming a document is done when it has no rollback path and no numeric gate, then calling rollout "an implementation detail."
- Agreeing that documents matter less in the AI-assisted era without pushing back on the premise.
- Any answer that never mentions a reader. Every question in this module is secretly "who is going to read this, and what will they do with it."

## Cheat card

```
ADR (Nygard, 2011-11-15) — 5 parts, 1-2 pages, in-repo doc/arch/adr-NNN.md
  Title(noun phrase) · Context(FACTS, value-neutral, forces in TENSION)
  Decision("We will...", active) · Status(proposed|accepted|superseded by NNN)
  Consequences(ALL of them, negative FIRST)
  Numbered monotonically, never reused. SUPERSEDED, never edited.
  Alternatives live INSIDE Context as forces. There is no alternatives section.
  Prose, not fragments. "Bullets kill people."

DESIGN DOC / RFC — mutable, pre-decision, seeks consensus
  TL;DR(3 sentences) · Context+scope · Goals · NON-GOALS · Design(1 diagram)
  Options(rejected ones argued at their STRONGEST) · Decision(+criterion)
  Consequences · Rollout(phases+numeric gates+rollback) · Open questions
  Google sweet spot: 10-20 pg large project, 1-3 pg mini doc. >20 pg = SPLIT.
  Rarely any code. Link the prototype instead.

NON-GOAL = could reasonably have been a goal, deliberately excluded.
  NOT a negated goal ("shouldn't crash" is wrong).
  Highest leverage: kills N comment threads at 4-48h round-trip each.
  Abuse test: would a reviewer accept it as a legit v1 boundary?

REJECTED OPTION, 3 rules: state it at its strongest in its advocate's words ·
  name the deciding CRITERION and admit it's a weighting · say what FLIPS it.

ARTIFACT PICKER
  ambiguous solution + need consensus ......... design doc / RFC
  decision made, want durable record .......... ADR
  no real tradeoff ............................ write the code (Google)
  prototyping ................................. build it, then write
  two people disagree, haven't talked ......... have the conversation
  cheap two-way door .......................... just do it
  audience of one ............................. send a message

REVIEW THAT CONVERGES
  state the ASK + the CLOSE DATE at the top
  pre-review with the 2 most likely blockers BEFORE going wide
  "Yes, if" not "No, because" (Squarespace) — forces a satisfying condition
  triage: blocking(fix) / non-blocking(fix silently) / preference(reply once)
  contentious? buy 25 min synchronous silent read (Amazon 6-pager, 2004)
  bikeshedding = Parkinson's law of triviality; decision in first 3 sentences

TEMPLATES WORTH STEALING FROM
  Rust RFC: Drawbacks("what does this FORECLOSE") · Rationale+alternatives ·
    Prior art · Unresolved questions · Future possibilities
  K8s KEP: test plan · graduation criteria · upgrade/downgrade · version skew ·
    Production Readiness Review (feature gate rollback, monitoring)
  MADR 4.0.0 (2024-09-17): considered options + decision outcome; 4 variants
  Amazon: 6-pager (4pg 2004 -> 6pg), read in silence 20-25 min; PR/FAQ

2026: in-repo ADRs feed coding agents alongside AGENTS.md/CLAUDE.md.
  YADR (YAML MADR, Mar 2026) = machine consumption is now a design constraint.
  Hygiene (stable numbers, accurate Status) matters more, not less.
```

## Sources

- [Documenting Architecture Decisions — Michael Nygard, Cognitect](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions.html) — accessed 2026-08-05
- [Architectural Decision Records (adr.github.io)](https://adr.github.io/) — accessed 2026-08-05
- [MADR — Markdown Any Decision Records](https://adr.github.io/madr/) and [adr/madr on GitHub](https://github.com/adr/madr) — accessed 2026-08-05
- [Design Docs at Google — Malte Ubl, Industrial Empathy](https://www.industrialempathy.com/posts/design-docs-at-google/) — accessed 2026-08-05
- [Design docs — A design doc — Malte Ubl](https://www.industrialempathy.com/posts/design-doc-a-design-doc/) — accessed 2026-08-05
- [Rust RFC template — rust-lang/rfcs `0000-template.md`](https://github.com/rust-lang/rfcs/blob/master/0000-template.md) — accessed 2026-08-05
- [Kubernetes KEP template — kubernetes/enhancements](https://github.com/kubernetes/enhancements/blob/master/keps/NNNN-kep-template/README.md) — accessed 2026-08-05
- [Kubernetes Enhancement Proposal process (KEP-0000)](https://github.com/kubernetes/enhancements/blob/master/keps/sig-architecture/0000-kep-process/README.md) — accessed 2026-08-05
- [PEP 1 — PEP Purpose and Guidelines](https://peps.python.org/pep-0001/) — accessed 2026-08-05
- [The Power of "Yes, if": Iterating on our RFC Process — Squarespace Engineering](https://engineering.squarespace.com/blog/2019/the-power-of-yes-if) — accessed 2026-08-05
- [Engineering Planning with RFCs, Design Documents and ADRs — The Pragmatic Engineer](https://blog.pragmaticengineer.com/rfcs-and-design-docs/) — accessed 2026-08-05
- [Staff-plus interview processes — Will Larson](https://lethain.com/staff-plus-interview-process/) — accessed 2026-08-05
- [Interviewing for Staff-plus roles — StaffEng](https://staffeng.com/guides/interviewing-staff-plus-roles/) — accessed 2026-08-05
- [Bikeshedding / Parkinson's law of triviality](https://en.wikipedia.org/wiki/Law_of_triviality) — accessed 2026-08-05
- `T13-code-review` — comment triage, compounding vs one-time cost, feedback that names a cost (this repo)

## Changelog
- 2026-08-05 — created

