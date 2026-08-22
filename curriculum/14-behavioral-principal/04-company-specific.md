# Amazon LPs, Google, Meta, Microsoft, Netflix, AI Startups

> **Track:** T14 Behavioral & Principal · **Time:** 1.5h · **Prereqs:** T14-star-bank · **Updated:** 2026-07-26
> **Module id:** `T14-company-specific` · **Tags:** sprint, behavioral

## The 30-second version

The same 30 stories from your STAR bank pass or fail depending on which company's rubric is scoring them, because each company optimises for something structurally different: Amazon for evidence against 16 named Leadership Principles with a Bar Raiser from outside the team holding veto power, Google for transcribable evidence that survives a hiring committee who never met you, Meta for speed and ownership at pace across two design rounds plus an AI-assisted coding round at E6+, Microsoft for domain depth with a final "As Appropriate" round tailored to whatever you were weakest on earlier, Netflix for peer-level conversational judgment against a written culture memo with no whiteboard, and AI labs for demonstrated build velocity through a graded work trial rather than for interview performance. Your resume maps unevenly onto these: the 8-service platform and the ~25% uplift are your Amazon and Meta leads, the OOM and MongoDB concurrency work are your Google depth leads, the vLLM and cost decisions are your AI-startup leads, and the multi-locale and multi-tenant authorization work is your Microsoft lead. The mistake is telling the same story in the same shape at all six; the fix is choosing which of the four or five available framings of each story you use.

## Why this gets asked

Company-specific prep is not a question they ask, it is the filter your answers are read through. The interviewer is scoring against a rubric they did not write and cannot see around, so a story that is excellent against Google's General Cognitive Ability axis and does not name a customer will score mid at Amazon regardless of quality. The deeper reason to know the loop structure is time allocation: knowing that Amazon will ask you roughly 12 to 15 LP questions with a Bar Raiser drilling each one tells you to prepare two stories per LP rather than one great story overall, and knowing that OpenAI's decisive round is a 48-hour graded work trial tells you that polishing behavioural answers for that loop is misallocated effort ([Interview Coder, OpenAI process 2026](https://www.interviewcoder.co/blog/openai-interview-process) — accessed 2026-07-26).

---

## Lineage: past → present → future

**What came before.** Through the 2000s the FAANG loops converged on a near-identical shape, four to five 45-minute rounds of algorithms plus one system design plus a culture chat, and the culture chat was largely unscored. The pain that killed the convergence was that the loops did not discriminate: everyone was hiring from the same pool with the same signal, false negatives were enormous, and the loops selected for interview preparation rather than for the job. Companies diverged deliberately in response. Amazon went furthest toward structure with the Leadership Principles and the Bar Raiser, a trained interviewer from outside the hiring team with veto power, which is an explicit institutional defence against a hiring manager lowering the bar to fill a role. Netflix went the opposite direction, removing structure almost entirely in favour of a written culture memo and senior-to-senior conversation. Google split the difference and pushed the decision *out* of the room entirely to a hiring committee scoring a written packet, which is a defence against interviewer variance rather than against manager incentive.

**Where it stands now.** Six meaningfully different regimes, and the differences are now large enough that prep does not transfer cleanly. Amazon: 16 LPs, 4 to 5 rounds with 2 to 3 LPs assigned per interviewer, Bar Raiser with veto. Google: four scored attributes (Role-Related Knowledge, General Cognitive Ability, Leadership, Googleyness) with a hiring committee reading written evidence. Meta: five rounds at E6 including one standard coding round, one AI-assisted coding round, two design rounds and a behavioural round, plus a Leadership Assessment before the onsite that replaces the phone screen at that level. Microsoft: competencies distributed across rounds ending in the As Appropriate round. Netflix: conversational, often no whiteboard, seven-ish interviews, keeper-test framing. AI labs: staged gates plus a paid work trial graded on shipped code. The live disagreement across all of them is what to do about AI assistance: Meta has made it an explicit round, OpenAI's policy varies by team with research generally AI-prohibited and design discussion sometimes AI-permitted, and most companies have an unenforced policy. The second live disagreement is whether take-homes are ethical at senior level, since they cost the candidate days and select for people with slack in their schedule; the AI labs pay for them, which is the current best answer.

**Where it's heading.** High confidence: **AI-assisted rounds become standard within two years**, because the alternative is testing a skill nobody uses. Expect the scored dimension to be judgment about what to accept, override and verify, which is a behavioural competency wearing a coding round's clothes. Medium confidence: **work trials spread from the AI labs to larger companies for senior roles**, because they predict better than interviews and the labs have normalised paying for them. Speculative: the LP-style named-value rubric spreading further, since it is the cheapest way to make interviewer notes comparable, though it also produces the rehearsed-answer problem that Bar Raisers exist to counter. Treat that last one as a plausible direction rather than a trend.

---

## Mental model

Six companies, one axis that explains most of the variation: **where the hiring decision is made, and what protects it from being wrong.**

```
   WHO DECIDES                    WHAT PROTECTS THE BAR         WHAT THAT MEANS FOR YOU

   AMAZON                         Bar Raiser: outside the        Every story gets drilled
   hiring manager + panel,        team, veto power, trained      until something breaks.
   Bar Raiser can veto            to probe past the script       Bring DEPTH per story.

   GOOGLE                         Hiring committee: never        Optimise for QUOTABLE
   committee, not the             met you, reads written         sentences. Anything that
   interviewers                   evidence only                  doesn't transcribe is lost.

   META                           Calibrated panel + level       Move FAST. Density of
   panel + hiring committee       guidelines; speed is           signal per minute is the
                                  itself a signal                thing being measured.

   MICROSOFT                      "As Appropriate" round         Your WEAKEST answer gets
   hiring manager, strong         tailored to your gaps          revisited. Note it and
   team weighting                                                prepare the second pass.

   NETFLIX                        Keeper test culture; the        Be a PEER, not a
   manager, high autonomy         written culture memo is         candidate. Disagree well.
                                  the actual rubric              Expect no scaffolding.

   AI LABS                        The work trial: graded          Your CODE decides it.
   founders/team, fast            production code, paid,          Interview polish is a
                                  48h                            secondary axis.
```

The practical consequence: **the same story needs four or five different framings, not four or five different stories.** Take S10, the 8-service platform.

```
   AMAZON     "2M+ enterprise users had no recommendation capability, and the
              customer problem was that a new employee got the same generic
              catalogue as a ten-year veteran. I owned it end to end..."
              → leads with the CUSTOMER, names ownership scope explicitly

   GOOGLE     "Eight services, 307 commits, 178,000 net lines, 2M+ users,
              ~25% engagement uplift. The decomposition criterion was
              independent scaling and independent failure, not data entities."
              → leads with QUOTABLE SPECIFICS the committee can read

   META       "No recommendation capability, 2M+ users, greenfield. I drew the
              boundaries on scaling profile, shipped the event path first so
              we could measure, and got ~25% engagement. Two of the eight
              I'd merge today."
              → COMPRESSED, ends on the self-critique, moves on

   MICROSOFT  "Multi-tenant, 2M+ users, and the isolation requirement drove
              the decomposition. Let me go into how tenant scoping worked
              across the vector index..."
              → leads into DOMAIN DEPTH, expects to be drilled later

   NETFLIX    "Honestly, eight was too many. Three scaling profiles justified
              three boundaries; the other five were tidiness. Here's what I'd
              do instead..."
              → PEER-LEVEL candour, treats the interviewer as a colleague

   AI STARTUP "Greenfield, no event pipeline, 2M+ users, shipped in about a
              year with 307 commits. First measurable win was ___. Cost per
              recommendation was ___."
              → SHIP VELOCITY and COST, in that order
```

---

## How it actually works

# AMAZON

## What they actually optimise for

Evidence. Not potential, not likeability, not the elegance of your design. A written record of specific past behaviour mapped to a named principle, from a candidate who does not fall apart when someone drills three layers past the summary. The Bar Raiser mechanism exists because hiring managers under pressure lower the bar, so Amazon inserted someone with no stake in filling the role and gave them a veto.

## Loop structure

Four to five back-to-back interviews. Each interviewer is assigned two to three specific Leadership Principles, and the panel collectively covers the full set, so **you will be asked roughly 12 to 15 LP questions in a day**. Every interview also has a technical component; there is no purely behavioural round. The Bar Raiser is pulled from a different team, is trained to probe for specifics, and holds veto power ([Exponent, LP interview guide 2026](https://www.tryexponent.com/blog/amazon-leadership-principles-interview) — accessed 2026-07-26). At Principal level the loop is longer, reported at seven to eight rounds, mostly technical and behavioural ([Glassdoor, Amazon Principal Engineer](https://www.glassdoor.com/Interview/Amazon-Principal-Engineer-Interview-Questions-EI_IE6036.0,6_KO7,25.htm) — accessed 2026-07-26).

In practice the LP weighting in SDE loops clusters around **Dive Deep, Deliver Results, Invent and Simplify, and Bias for Action** ([ResumeAdapter, LP guide](https://www.resumeadapter.com/companies/amazon/leadership-principles) — accessed 2026-07-26). Prepare those four hardest.

## The bar at staff and principal

"Deliver Results" is described in Amazon's own Principal Engineering tenets as a **low bar** for a Principal Engineer; the expectation is lasting impact that echoes through the technology, the product and the company. Principal Engineers are expected to bring clarity to complexity, frame each problem in its customer and business context and reduce it to its essence, stay hands-on and lead by example, and educate the organisation about trends and approaches rather than only consuming them ([Amazon Principal Engineering Tenets](https://mukteshkrmishra.medium.com/amazon-principal-engineering-tenets-947a00cc7233) — accessed 2026-07-26).

Translate that into three things you must evidence, and be honest about which you are thin on:
1. **Impact that outlived your involvement.** Something still running, still used, still the standard.
2. **Simplification of something complex.** Your strongest available evidence and the one Amazon weights heavily.
3. **Influence beyond your own code.** A pattern others adopted, a decision that changed how a team works.

The third is the weakest area of your resume and you should know that going in. `[CONFIRM: how many engineers and teams consume the MCP tool contracts, the JWT rotation mechanism, and the skill resolution engine. That number is what evidences principal scope and it is not on your resume.]`

## All 16 LPs, mapped to your stories

| Leadership Principle | Lead story | Backup | The specific sentence to open with |
|---|---|---|---|
| **Customer Obsession** | S18 GenAI content creator | S05 22-locale, S24 Query Crafter | "Users searched for topics the catalogue didn't have, got nothing useful, and left. The only signal we kept was a failed query." |
| **Ownership** | S06 cross-tenant authz | S10 platform, S29 Credit Suisse | "Nobody assigned this to me. I found it, and I had to decide how loudly to escalate." |
| **Invent and Simplify** | S13 Java→Python, -3,447 lines | S03 ClickHouse over Weaviate, S27 | "Most of the 3,447 lines was Spring Batch scaffolding, not business logic. That's why 812 lines of Python is a faithful port." |
| **Are Right, A Lot** | S14 CMAB over supervised ranker | S03, S11 revisiting own design | "A supervised ranker trained on logged clicks learns the previous policy's preferences, so new content never gets shown." |
| **Learn and Be Curious** | S30 career arc + 2 Springer papers | S15 vLLM internals | "I went deep on inference internals rather than API surfaces, because the API surface changes every quarter." |
| **Hire and Develop the Best** | `[CONFIRM: your weakest LP. Mentoring, onboarding, code review culture, interviewing. Write one story.]` | — | — |
| **Insist on the Highest Standards** | S08 golden baseline + 200 tests | S06, S07 parameterized SQL | "Releases were gated on manual spot-checks. I decided that was the actual blocker and built the baseline alongside feature work." |
| **Think Big** | S01 A2A + FastMCP | S10 platform, S28 Expedia | "The old pipeline could tell you what a course covered. It could not reason about what the catalogue was missing." |
| **Bias for Action** | S29 Credit Suisse RPA from a BA seat | S09 async ingestion, S26 chatbot | "The sanctioned path was a platform request measured in quarters. I automated it with Python and RPA instead." |
| **Frugality** | S15 vLLM self-host | S17 Bedrock batch, S16 benchmarking | "Per-token pricing scales linearly with success. I split by workload shape rather than picking one vendor." |
| **Earn Trust** | S06 escalating the authz finding | S19 fleet-wide rotation, S11 | "I escalated immediately rather than quietly patching, because a silent fix leaves nobody able to assess exposure." |
| **Dive Deep** | S04 OOM on 1.2M rows | S21 Mongo races, S20 Redis | "It was killed with no Python traceback, which tells you it's the kernel OOM killer, not an application exception." |
| **Have Backbone; Disagree and Commit** | S05 rejecting language auto-detect | S06, S07 rejecting WAF+sanitisation | "A reviewer suggested auto-detecting the language. I said no, and the reason is that detection on short strings is unreliable and a wrong detection is silent." |
| **Deliver Results** | S28 4.5h → 30min (~89%) | S10 ~25% uplift, S24 50% turnaround | "4.5 hours meant one marketing optimisation cycle per working day. The runtime was the constraint on the business process." |
| **Strive to be Earth's Best Employer** | `[CONFIRM: thin. Team practices, on-call health, documentation, unblocking others.]` | — | — |
| **Success and Scale Bring Broad Responsibility** | S18 generated content into an enterprise catalogue | S06 multi-tenant data isolation | "Auto-generating a course into an enterprise catalogue is a content-quality and liability question, not just an engineering one." |

**Two gaps, and they are real.** Hire and Develop the Best, and Strive to be Earth's Best Employer. Both are people-facing and neither is on your resume. At Principal level you will be asked about the first, close to certainly. Write one story before an Amazon loop. `[CONFIRM: mentoring, onboarding someone onto the platform, raising the code review bar, changing the on-call rotation, or running interviews. Something real, however small.]`

## Amazon-specific answer mechanics

- **The Bar Raiser will drill until something breaks.** Depth per story matters more than story count. Know one level below the summary of every number you cite.
- **First person singular, aggressively.** Amazon's interviewers are trained to isolate personal contribution, and "we" in the Action section is the most common cause of a down-vote on a strong story.
- **Two stories per heavily weighted LP.** You will be asked Dive Deep more than once by different interviewers, and repeating a story across rounds shows up in the shared write-up.
- **Name the customer, always.** Even in an infrastructure story. For S04, the OOM blocked the skill intelligence rollout, which blocked recommendations, which is customer impact.
- **Have a "disagreed and was wrong" story.** Disagree and Commit is two clauses and most candidates evidence only the first. `[CONFIRM: pick one.]`
- **Do not inflate.** A fabricated number is the specific thing the Bar Raiser is trained to find, and the ~25% engagement figure is your most attackable claim. Prepare the measurement method before anything else.

## Lead with, at Amazon

1. **S10** (8-service platform) for scope and Ownership.
2. **S04** (OOM) for Dive Deep, which is the most heavily weighted engineering LP.
3. **S13** (Java→Python) for Invent and Simplify, because deleting 3,447 lines is a rarer claim than building something new.
4. **S06** (authz) for Earn Trust and Highest Standards.
5. **S28** (4.5h → 30min) for Deliver Results, since it is your cleanest baseline-to-outcome number.

---

# GOOGLE

## What they actually optimise for

Structured reasoning that survives transcription. Google evaluates four attributes: Role-Related Knowledge, General Cognitive Ability, Leadership, and Googleyness. The decisive mechanism is that after the loop, the interviewers' written feedback goes to a **hiring committee of senior Googlers who never interviewed you and do not know the hiring team**, and they score the strength of the written evidence rather than your presence or likeability ([ResumeAdapter, Google process 2026](https://www.resumeadapter.com/companies/google/interview-process) — accessed 2026-07-26).

The direct consequence, and it is the single most actionable fact in this module: **anything that does not survive being written down does not count.** Rapport, energy, gesture, and the interviewer's sense that you seemed competent all evaporate. "54,486 skills across 22 locales, resolved through a tiered cascade so tenant vocabulary wins over a global match" survives. "Large-scale multilingual skill system" does not.

## Loop structure

At L6 the reported structure is two system design rounds (one product or applied, one infrastructure or architecture), a technical leadership round sometimes labelled Googleyness++ or leadership and impact, and one to two coding rounds. There is real variance: some candidates see two coding and two design, some see three design rounds with no separate role-related-knowledge interview, and some never get a dedicated General Cognitive Ability round ([Hello Interview, Google L6](https://www.hellointerview.com/guides/google/l6) — accessed 2026-07-26). Coding is still real at L6; do not skip it.

## The bar at staff (L6) and senior staff (L7)

- **GCA** measures whether your reasoning is structured and adaptive, not whether you reached the right answer. Say your structure out loud before you use it.
- **Leadership** at L6 means technical direction-setting and cross-team influence, not people management. Your S19 (fleet-wide rotation) and S24 (Query Crafter unblocking non-technical stakeholders) are the closest available evidence.
- **Googleyness** explicitly includes intellectual humility, comfort with ambiguity, bias to action, and collaboration, and it must be demonstrated through described behaviour rather than stated values: noticing that a disagreement was blocking progress and scheduling one-on-ones counts, "I value collaboration" does not ([Prepfully, Googleyness guide](https://prepfully.com/interview-guides/googles-googleyness-interview) — accessed 2026-07-26).

## Google-specific answer mechanics

- **Speak in complete, quotable sentences.** Not "so we sharded it and that helped" but "I sharded on tenant id, accepting that the largest tenant becomes a hot partition, which I handled with a composite key."
- **Lead with the odd numbers.** 54,486. 3,447. 307. 178,000. 1.2 million. They are credible because they are specific and they transcribe cleanly.
- **Announce your reasoning structure.** "There are three constraints and I'll take them in order of how much they narrow the design." That sentence is GCA evidence in itself.
- **Intellectual humility needs a real story.** S11 (criticising your own eight-service decomposition) and the attribution gap in S25 (you cannot say whether the knowledge graph earned its maintenance cost) are your two. A trivial regret does not score.
- **Do not name-drop Google's own systems as arguments.** "Spanner does it this way" is not a reason; your constraint is.

## Lead with, at Google

1. **S04** (OOM) for RRK and GCA. It is a mechanism-level story with a clean symptom-to-cause chain, and it transcribes well.
2. **S02 / S03** (skill resolution and the ClickHouse decision) for RRK depth with the numbers doing the work.
3. **S11** (revisiting the decomposition) for Googleyness and intellectual humility.
4. **S24** (Query Crafter) for Leadership, since the impact was on people outside your team.
5. **S14** (CMAB) for GCA, because it is a reframe from prediction to exploration and that reframe is the reasoning artifact.

---

# META

## What they actually optimise for

Ownership at pace. Meta's behavioural round, known internally as "Jedi", is 45 minutes on values and leadership signals and focuses on how you work: ownership, collaboration, conflict, execution under ambiguity, and learning from mistakes ([ClavePrep, Meta 2026](https://claveprep.com/blog/meta-interview-process-2026-guide) — accessed 2026-07-26). Speed is itself a scored dimension, in the sense that Meta rounds are dense and a candidate who needs six minutes of clarification is spending signal budget.

## Loop structure

At E6 the reported onsite is **one standard coding round, one AI-assisted coding round, one architecture round, one design round, and one behavioural round**, plus a **Leadership Assessment interview before the onsite that replaces the standard phone screen at this level** and is roughly half behavioural and half coding. At E7 and above the freed time goes into deeper system design, deeper behavioural, and an additional cross-functional round graded on judgment in ambiguous situations ([ClavePrep, Meta 2026](https://claveprep.com/blog/meta-interview-process-2026-guide); [DGLearning, inside the Meta 2026 loop](https://dglearning.substack.com/p/inside-the-meta-2026-loop-rounds) — accessed 2026-07-26).

**The AI-assisted coding round is the notable 2026 change and the stated intent is explicit:** at senior level Meta is not testing whether you can write a sorting algorithm, it is testing whether you can direct work, including AI-generated work, with sound judgment. Prepare for it as a judgment round: when do you accept a generated solution, when do you override it, how do you verify it, and what do you refuse to ship without reading. You have a real answer available here from your own practice `[CONFIRM: how you actually use coding assistants on the platform work, and one instance where you overrode or rejected generated code and why]`.

## The bar at E6 (staff) and E7

At E6 the behavioural expectations are specifically scoped: for a disagreement question the staff-level answer involves working through a disagreement with **two or more teams** on the direction of a large project, and for an impact question it is a project with **large impact on the org**, not on the team. Anything scoped to a single team reads as E5.

That is a direct problem for your story set: most of your stories are within one platform and one team. Your available multi-team stories are S19 (a credential mechanism across a service fleet), S24 (Query Crafter, where the users were non-technical stakeholders in other functions), S29 (Credit Suisse, engineering work from a BA seat), and S09 (Skillmaster integrated into the multi-tenant provisioning platform, which is another team's system). `[CONFIRM: which of these genuinely involved another team, and how many.]`

Meta also explicitly scores **learning from mistakes**, so a real failure with a real cost is not optional here.

## Meta-specific answer mechanics

- **Compress.** Sixty-second stories, then stop. Meta interviewers cover more ground per round than Amazon's and a three-minute unprompted answer costs you a question.
- **End on the self-critique.** "Two of the eight I'd merge today" is a stronger close at Meta than at Amazon, because growth mindset and learning from mistakes are explicitly scored.
- **Scope up, honestly.** Where a story genuinely crossed teams, say which teams and how many. Where it did not, do not inflate it; use a different story.
- **Have the AI-assisted answer ready.** This is the one round where 2026 prep differs materially from 2024 prep.
- **Practicality over elegance.** Meta design rounds reward the design you would actually ship this half.

## Lead with, at Meta

1. **S10** (8-service platform) compressed to 60 seconds, ending on the merge critique.
2. **S19** (fleet-wide rotation) for cross-service ownership.
3. **S11** (own decomposition critique) for learning from mistakes.
4. **S21** (Mongo races, event loop) for the coding and debugging rounds, since it is concrete and load-dependent.
5. **S29** (Credit Suisse) for execution under ambiguity outside your remit.

---

# MICROSOFT

## What they actually optimise for

Domain depth plus growth mindset, assessed across rounds rather than in one. The distinctive mechanism is the final **"As Appropriate" (AA) round**, usually run by a Principal Engineering Manager or a Partner-level leader, and it is called As Appropriate because it is tailored to how you performed in the earlier rounds; interviewers sync or share notes beforehand ([OphyAI, Microsoft guide](https://ophyai.com/blog/company-guides/microsoft-interview-guide) — accessed 2026-07-26).

Reading the AA round is a real skill. If the interviewer is relaxed and mostly pitching the team, you are in sell mode and the earlier rounds went well. If they aggressively test technical gaps, you are borderline and this is the last chance to close them. Reported AA rounds at senior level cover data modelling, system design and coding with the hiring manager, and the format is often a project-focused discussion driven by the interviewer rather than a formal evaluation.

**The actionable consequence:** whatever you answer weakest in round two will be revisited in round five. Write it down between rounds and prepare the second pass. Almost nobody does this and it is nearly free.

## Loop structure

Recruiter screen, technical phone screen, then four to five onsite rounds distributed across coding, system design, domain depth and behavioural, ending in the AA round. At Principal level expect heavier weighting on architecture and cross-team influence, and expect the hiring manager's opinion to carry more weight than at Google, since there is no equivalent of the hiring committee removing the decision from the room.

## The bar at Principal (L65/L66) and Partner

- **Depth in your actual domain,** not breadth across everything. Microsoft is comfortable hiring a specialist.
- **Growth mindset** is a genuine rubric item, not marketing. The "learn-it-all not know-it-all" framing means an "I was wrong and here is what I changed" story scores directly.
- **Enterprise realities count here more than anywhere else.** Multi-tenancy, compliance, global readiness, security, backward compatibility, migration of installed customers. This is Microsoft's actual world, and your resume is unusually well matched to it.

## Microsoft-specific answer mechanics

- **Lead with the enterprise-shaped stories.** S05 (22 locales, global readiness), S06 (multi-tenant isolation and security), S09 (multi-tenant provisioning), S13 (migration with a cutover strategy). These are the closest fit of any company on this list.
- **Be explicit about backward compatibility and migration.** Microsoft engineers live with installed bases and a candidate who volunteers a rollback plan reads as one of them.
- **Track your own weak answers between rounds.** For the AA round.
- **Do not oversell.** Microsoft's culture penalises the confident overclaim more than Amazon's does, and the growth-mindset framing makes a calibrated answer safer than a bold one.

## Lead with, at Microsoft

1. **S05** (22-locale hardening) for global readiness and attention to correctness.
2. **S06** (cross-tenant authorization) for security ownership in a multi-tenant product.
3. **S13** (Java→Python migration) for legacy modernisation with a safe cutover.
4. **S02** (skill resolution engine) for domain depth.
5. **S11** or the S25 attribution gap for growth mindset.

---

# NETFLIX

## What they actually optimise for

Whether you operate as a senior peer with minimal scaffolding. Netflix's rounds are conversational, domain-specific, and frequently run **without any shared diagramming tool**; multiple candidates report completing the system design round with no whiteboard at all, which forces you to communicate a design verbally ([Exponent, Netflix system design 2026](https://www.tryexponent.com/blog/netflix-system-design-interview) — accessed 2026-07-26). Reported loops run to around seven interviews mixing technical and behavioural or product-sense rounds.

The cultural frame is the **keeper test** ("would I fight to keep this person") and the written culture memo, which functions as the actual rubric ([ClavePrep, Netflix 2026](https://claveprep.com/blog/netflix-interview-process-2026-keeper-test-culture-deck) — accessed 2026-07-26). The memo's live values, candour, context over control, high talent density, and freedom with responsibility, are what your stories are being read against.

## The bar at senior and staff

- **You are expected to have driven, not been directed.** Netflix's model is context rather than control, so a story where you executed someone else's plan reads badly regardless of the outcome.
- **Candour is scored positively, including toward the interviewer.** Saying "eight services was too many and here is what I would do instead" lands better here than anywhere else on this list.
- **Judgment under high autonomy.** The relevant question is what you decided when nobody told you what to do. S06 (found it, escalated it, fixed the class), S29 (automated from a BA seat), S13 (proposed the migration) are your best.

## Netflix-specific answer mechanics

- **Practise verbal architecture.** Number your components, state direction explicitly, name them once and reuse the names. Rehearse one flagship system with your hands behind your back. See `T14-design-communication` for the technique.
- **Be candid about failures without hedging.** "I do not know whether the knowledge graph earned its maintenance cost, because I shipped it alongside content embeddings and never isolated the contribution" is a Netflix-shaped answer.
- **Do not over-structure.** A rigid STAR recitation reads as corporate here. Same content, conversational delivery.
- **Expect fewer prompts.** If the interviewer goes quiet, keep going. Silence is not disapproval, it is the absence of scaffolding.
- **Be ready to disagree with the interviewer.** Candour is a two-way value at Netflix, and agreeing with everything reads as low talent density.

## Lead with, at Netflix

1. **S11 / S10 together** as one candid story: what you built, why the boundaries were partly wrong, what you would do instead.
2. **S15** (self-hosting vLLM) for a build-versus-buy judgment call with an honest gap (no cost model).
3. **S06** (authz finding) for judgment under autonomy.
4. **S28** (4.5h → 30min) for impact, framed as cycle time rather than runtime.
5. **S25** attribution gap, as a genuinely candid answer about what you cannot prove.

---

# AI STARTUPS AND FRONTIER LABS

## What they actually optimise for

Demonstrated build velocity and technical taste, assessed through work rather than through interview performance. This is the regime where your prep effort should be allocated differently from everywhere else on this list.

**OpenAI** runs a multi-stage skills-first loop: resume screen, recruiter call, a role-specific skills assessment, then a final loop of four to six interviews, typically four to eight weeks end to end. The distinguishing stages are a technical screen using a **progressive gate format** where one problem gets harder across roughly four stages and most candidates report needing to clear at least two gates, and a **paid 48-hour work trial** graded on shipping speed, code quality, design choices and how you write tests. The process varies meaningfully by team, and the AI-tool policy in coding rounds varies by team too: research is generally AI-prohibited in technical rounds, infrastructure is generally AI-prohibited in coding and sometimes AI-permitted in design discussion ([Interview Coder, OpenAI 2026](https://www.interviewcoder.co/blog/openai-interview-process); [techinterview, OpenAI team-by-team 2026](https://www.techinterview.org/post/3233474915/openai-interview-process-2026-team-by-team/) — accessed 2026-07-26).

**Anthropic** runs a five-stage loop over roughly four to six weeks for engineering (four to seven for research): recruiter screen, a 60-minute technical phone screen with one medium-hard problem, a take-home, and an onsite. The coding round is described as writing code fast to a spec and refactoring quickly as constraints are added per stage, in a four-level assessment where you implement a system and iteratively extend it. The bar for written reasoning is high, the coding bar is comparable to Google or Meta, and cultural fit specifically means taking safety seriously without being a doomer ([Perspective AI, Anthropic Applied AI Engineer process 2026](https://getperspective.ai/blog/anthropic-applied-ai-engineer-interview-process-frontier-lab-2026); [IGotAnOffer, Anthropic process](https://igotanoffer.com/en/advice/anthropic-interview-process) — accessed 2026-07-26).

## The bar

- **Ship velocity is the primary axis.** Not architectural elegance. The work trial grades what you actually produced in 48 hours, including tests.
- **Iterative refactoring under changing requirements** is the specific coding skill both labs test, and it is different from the leetcode skill. Practise: implement to a spec, then absorb three new constraints without rewriting from scratch.
- **Cost and evaluation literacy.** These are the two things candidates most often lack and that these teams live with daily.
- **Mission alignment must be specific.** Generic enthusiasm reads worse than a concrete technical opinion about the problem space.
- **Written reasoning is scored.** Especially at Anthropic. If there is a written component, treat it as a primary round rather than an administrative step.

## What is strong and weak about your profile here

**Strong, and lead with these:**
- **S15 / S16** (self-hosted vLLM on SageMaker, continuous batching, PagedAttention, KV cache sizing, instance benchmarking). This is exactly the depth these teams want and it is your single best-matched story on this list.
- **S01** (A2A + FastMCP multi-agent replacing single-shot RAG). Current, protocol-level, and you can defend the multi-agent-versus-single-agent decision with a stated test.
- **S23** (async LLM rate limiting from distributed executors, and the per-executor multiplication trap). Small, specific, and it demonstrates you have actually run LLM workloads at concurrency.
- **S04** (OOM at 1.2M rows) for debugging depth.
- **S08** (golden baseline for a non-deterministic system) for evaluation literacy, which is rare and valued.

**Weak, and know it:**
- **The evaluation story is thinner than the systems story.** RAGAS and DeepEval are on your skills list; the resume does not show them producing a decision. `[CONFIRM: whether you ran a real eval that changed a design choice. If yes, that becomes a first-class story here.]`
- **No cost model for the self-hosting decision.** These teams will ask. Have the arithmetic or say plainly that you optimised for throughput and control and never modelled break-even.
- **No open-source or public artifact.** `[CONFIRM: github.com/hari2353 content. A public repo, a write-up of the OOM fix or the KV-cache sizing work, or an MCP server would materially help here and costs a weekend.]`
- **Your metrics are engagement metrics.** In a lab, "~25% engagement uplift" is a product number and lands weakly. Lead with throughput, cost per token, latency and reliability instead.

## AI-startup-specific answer mechanics

- **Allocate prep to the work trial, not the behavioural round.** For OpenAI and Anthropic the work trial is the decisive round and it is the one candidates most underprepare.
- **Practise spec-to-code-to-refactor.** Take a small system, implement it, then add three constraints in sequence without starting over. That is the literal format.
- **Have a cost-per-request number for something you built.** Anything. It signals a category of thinking most candidates lack.
- **Have a specific technical opinion about the space.** Not "AI is transformative" but something arguable: that most multi-agent systems are one agent with extra latency, that evaluation is the actual bottleneck in production LLM systems, that self-hosting is usually wrong below a volume threshold. You hold all three of those defensibly.
- **Safety and responsibility without performance.** S18 (guardrails on auto-generating content into an enterprise catalogue) and S06 (multi-tenant data isolation) are genuine, concrete answers. Use them rather than abstract statements.

## Lead with, at an AI lab or startup

1. **S15 / S16** (vLLM serving, KV cache, instance benchmarking).
2. **S01** (A2A + FastMCP, with the multi-agent-versus-single-agent test stated).
3. **S23** (async LLM rate limiting under distributed concurrency).
4. **S08** (evaluating a non-deterministic system with a golden baseline).
5. **S04** (OOM) for debugging.

---

## Practical exercise (replaces "Build it from scratch")

About 90 minutes. The work here is reframing, not writing new stories.

**Block 1 (25 min) — The six-framing drill.** Take S10 and S04. Write the opening sentence for each in all six regimes (Amazon customer-first, Google quotable-specifics, Meta compressed-with-self-critique, Microsoft domain-depth, Netflix candid-peer, AI-lab velocity-and-cost). Twelve sentences. Say each aloud. The point is to feel how much the framing changes while the content does not.

**Block 2 (20 min) — Close the two Amazon gaps.** Write one story for **Hire and Develop the Best** and one for **Strive to be Earth's Best Employer**. They can be small: onboarding someone onto the recommendation platform, raising the review bar, writing the runbook that stopped a recurring page, changing something about on-call. Small and true beats large and invented, and you cannot go into an Amazon Principal loop without them.

**Block 3 (15 min) — Multi-team audit.** For Meta E6, list every story that genuinely involved another team, and for each name the teams and what the coordination actually was. If the list has fewer than three entries, that is your honest scope limitation and you should know it before the loop rather than discover it in the Leadership Assessment.

**Block 4 (15 min) — The AI-assisted coding answer.** Write and rehearse a 60-second answer to "how do you work with AI coding tools, and tell me about a time you overrode one." This is a required Meta E6 answer in 2026 and it will appear elsewhere within the year. `[CONFIRM: a real instance.]`

**Block 5 (15 min) — Retarget your numbers.** Build two versions of your headline metric set: the product version (2M+ users, ~25% engagement, 50% turnaround) for Amazon, Meta and Microsoft, and the systems version (throughput, cost per million tokens, p99, 1.2M rows, 2.5 GB index, KV-cache-bound concurrency) for AI labs and infrastructure roles. Know which set you are in within the first thirty seconds of a round.

---

## How it's done in production

### One-page comparison

| | Amazon | Google | Meta | Microsoft | Netflix | AI labs |
|---|---|---|---|---|---|---|
| **Rubric** | 16 named LPs | RRK / GCA / Leadership / Googleyness | ownership, conflict, ambiguity, mistakes | competencies + growth mindset | written culture memo | ship velocity + taste |
| **Decision made by** | panel + hiring manager, Bar Raiser veto | hiring committee who never met you | panel + committee | hiring manager, strong team weight | manager, high autonomy | founders/team, fast |
| **Rounds** | 4-5 (7-8 at Principal) | 4-6, often 2 design at L6 | 5 at E6 + Leadership Assessment | 4-5 + As Appropriate | ~7 | staged gates + paid work trial |
| **Distinctive mechanism** | Bar Raiser | written packet to committee | AI-assisted coding round | AA round tailored to your gaps | no whiteboard, keeper test | 48h graded work trial |
| **Behavioural weight** | very high | medium-high | high | medium | high (as culture fit) | medium |
| **Coding still real at senior?** | yes | yes | yes, plus AI-assisted | yes | yes | yes, gate format |
| **Your best story** | S10, S04, S13 | S04, S02/S03, S11 | S10, S19, S11 | S05, S06, S13 | S11/S10, S15 | S15/S16, S01, S23 |
| **Your biggest risk** | thin on Hire and Develop; the ~25% number | too vague to transcribe | scope inside one team | overclaiming | over-structuring | no cost model, no public artifact |

### Failure-mode table

| Symptom | Cause | Fix |
|---|---|---|
| "Strong stories, weak LP mapping" (Amazon) | Told the story without naming the principle's behaviour | Open with the sentence from the LP table above. Lead with the behaviour the LP names. |
| Rejected after a strong-feeling Google loop | Answers did not survive transcription | Complete sentences, odd specific numbers, announced reasoning structure. |
| "Scope appears limited to own team" (Meta E6) | All stories inside one platform | Lead with S19, S24, S29. Do not inflate the others. |
| AA round aggressively tests one area (Microsoft) | You were weak there in round two | Track your weak answers between rounds and prepare the second pass. |
| "Did not feel like a peer" (Netflix) | Waited for prompts, over-structured, agreed with everything | Keep talking through silence. Disagree once, well. |
| Failed the work trial after strong interviews (AI labs) | Prep allocated to interview polish rather than shipping | Practise spec-to-code-to-refactor under a clock, with tests. |
| Bar Raiser broke a number | Cited a metric without its measurement method | The ~25% figure. Prepare the method before anything else in your prep. |
| Same story appeared in three write-ups | No per-company lead order | Use the "lead with" lists. Reframe explicitly if you must reuse: "I mentioned the platform earlier; let me take the security angle." |
| "Enthusiastic but no technical opinion" (AI labs) | Generic mission alignment | Bring one arguable technical position and defend it. |
| Asked about AI-assisted coding, had nothing | 2024-era prep | Block 4 of the exercise. |

---

## Tradeoffs & when NOT to use it

- **Do not over-tailor to the point of sounding coached.** An answer that name-checks a Leadership Principle explicitly ("this really demonstrates my Customer Obsession") is worse than one that simply exhibits the behaviour. Tailor the framing and the lead order; do not narrate the rubric.
- **Company research has diminishing returns fast.** Knowing the loop structure and the rubric is high value. Memorising the company's stated mission statement is not, and reciting it reads as preparation for the wrong thing.
- **The published process is frequently wrong for your specific loop.** Reported structures vary by team, level, region and recruiter. Ask the recruiter directly what the rounds are; they will usually tell you, and asking is a positive signal rather than a neutral one.
- **Do not apply the LP framework at a startup.** A twelve-person company has no rubric and a founder who wants to know whether you can ship. Structured STAR reads as heavyweight there.
- **Do not use Netflix-style candour at Amazon without the recovery.** "Eight services was too many" is excellent at Netflix and needs a completion at Amazon: what you would do instead, and what the trigger for the change is. Amazon wants Are Right A Lot alongside the self-criticism.
- **Do not lead with product metrics at an infrastructure or lab role.** "~25% engagement uplift" is your strongest number in three of these six regimes and one of your weakest in the other three. Know which room you are in.
- **Do not treat these six as exhaustive.** Apple, Databricks, Snowflake, Stripe and the AI infrastructure companies each differ again, and the transferable skill is asking what the rubric is rather than memorising six of them.
- **Do not let tailoring override truth.** If Meta wants multi-team scope and your story is single-team, the correct move is to use a different story or to state the scope accurately, not to inflate. Inflated scope collapses under a follow-up about who the other teams were and what they wanted.

---

## Interview questions

### Q1 — Amazon: tell me about a time you dove deep to find a root cause.
**Testing:** Dive Deep, the most heavily weighted engineering LP.
**Answer:** S04. Lead with the symptom, because that is what proves you were there: killed with no Python traceback, which is the kernel OOM killer rather than an application exception. Then the rejected easy fix, then the mechanism, then the verification across a full run rather than one page.
**Follow-up trap:** *"What did the data tell you that you did not expect?"* That pagination alone did not fix it, because memory still ratcheted across pages, which pointed at allocator and GC behaviour rather than at the query. A story where the data confirmed your first guess evidences a lucky guess, not Dive Deep.

### Q2 — Amazon: tell me about a time you had to develop someone.
**Testing:** Hire and Develop the Best, which is your thinnest LP.
**Answer:** `[CONFIRM: you need to write this one. Candidates: onboarding someone onto the recommendation platform, raising the code review bar, the 200+ tests as an enabling artifact for others, or running interviews.]`
**Follow-up trap:** *"What did they do differently afterwards?"* The answer must include a change in the other person's behaviour, not just that you helped them. Development stories without an observable outcome in the other person read as "I answered questions."

### Q3 — Google: walk me through the hardest technical problem you have solved.
**Testing:** RRK and GCA, scored from a written transcript.
**Answer:** S04 or S02, in complete quotable sentences with the specific numbers. "1.2 million multilingual rows, 54,486 skills, 22 locales" transcribes; "a large multilingual corpus" does not.
**Follow-up trap:** *"What would you have done if pagination had not fixed it?"* Have the branch ready: if memory growth were unbounded over time rather than proportional to input, that is a leak rather than a batching problem, and the next step is object-graph inspection to find what is retaining references. Naming the diagnostic fork proves method rather than luck, and GCA is specifically scoring adaptive reasoning.

### Q4 — Google: tell me about a time you changed your mind.
**Testing:** Googleyness, specifically intellectual humility, which must come through described behaviour rather than stated values.
**Answer:** S11. You went back to your own decomposition criterion and tested each boundary against it rather than defending the whole design, and the evidence was deploy coupling: services that always shipped together were one service plus a network hop.
**Follow-up trap:** *"Did you actually change anything?"* If no consolidation happened, say so and say what you did instead: documented the recommendation and the trigger conditions. Claiming a change you did not make is a worse answer than an honest documented recommendation.

### Q5 — Meta: tell me about a project with impact beyond your team.
**Testing:** E6 scope. Team-scoped answers read as E5.
**Answer:** S24 (Query Crafter unblocked non-technical stakeholders in other functions, 50% turnaround reduction) or S19 (a credential mechanism adopted across a service fleet). Name the other teams and what the coordination actually was.
**Follow-up trap:** *"How many teams, and did they adopt it because you convinced them or because you owned it?"* The honest answer is usually both, and the interesting part is what you did to make adoption easy: a versioned contract rather than a shared library, a migration path, documentation. Adoption you had to mandate is weaker evidence than adoption people chose.

### Q6 — Meta: how do you work with AI coding tools? Tell me about a time you overrode one.
**Testing:** the 2026 addition. Judgment about directing generated work.
**Answer:** `[CONFIRM: a real instance.]` The shape: where you use them (boilerplate, test scaffolding, unfamiliar API surfaces), where you do not (anything with a concurrency or authorization invariant), and how you verify. Then a concrete override with the reason.
**Follow-up trap:** *"How do you know the generated code is correct?"* Naming your verification method specifically is the whole answer: tests you wrote yourself rather than generated ones, reading the diff rather than the summary, and a category rule about what you will not accept unread. Your S06 authorization work and S21 concurrency work are exactly the categories where generated code is most dangerous, and saying so is a strong, specific answer.

### Q7 — Microsoft: tell me about making something work for enterprise customers globally.
**Testing:** global readiness and enterprise depth, which is Microsoft's actual world.
**Answer:** S05. The precedence chain, Unicode-aware normalisation rather than ASCII lowercasing, locale-driven model routing, and the reason auto-detection was rejected: unreliable on short strings and silent when wrong.
**Follow-up trap:** *"How did you know it was fixed?"* Fallback rate. How often the system silently falls back to `en_us` turned out to be the most useful metric in the system, and you added it later than you should have. Volunteering that it was added late is the growth-mindset beat and Microsoft scores it.

### Q8 — Microsoft: what is something you were wrong about?
**Testing:** growth mindset, a real rubric item here.
**Answer:** S11, or the S25 attribution gap: you cannot say whether the knowledge graph earned its maintenance cost, because you shipped it alongside content embeddings and never isolated the contribution.
**Follow-up trap:** *"What did that cost?"* A component you cannot justify and therefore cannot confidently remove or defend. A "wrong" with no cost is not a wrong, and this is the specific question where a costless answer fails.

### Q9 — Netflix: tell me about a decision you made that others disagreed with.
**Testing:** candour and judgment under autonomy.
**Answer:** S06 (escalating the authorization finding loudly rather than patching quietly) or S13 (proposing a migration nobody asked for). Describe the other position as reasonable, then your evidence, then the outcome including where you lost.
**Follow-up trap:** *"What if you had been wrong?"* Have a real answer. For S06: escalating a security finding that turns out to be lower severity than you thought costs credibility and some people's time, and that is an acceptable price for the asymmetry, since the cost of under-escalating a real cross-tenant exposure is a contractual and reputational event. Naming the asymmetry explicitly is the judgment being tested.

### Q10 — AI lab: why did you self-host instead of using an API?
**Testing:** cost and infrastructure literacy, and whether you have a framework or a preference.
**Answer:** S15. Volume growth with per-token pricing, tenant data-handling expectations, and, critically, that you did not self-host everything: Bedrock batch for the offline path, hosted frontier models for tasks that need them. Split by workload shape.
**Follow-up trap:** *"What was the break-even?"* If you did not model it, say so directly and say that is the gap: you optimised for throughput and control and can defend both, and a cost model is what would have made the decision reviewable outside engineering. Then offer the derivation live: instance hourly cost times utilisation against per-million-token pricing at your volume. An interviewer who runs GPU capacity will respect the derivation and will catch an invented number.

### Q11 — AI lab: what is your view on multi-agent systems?
**Testing:** technical taste, and whether you have an opinion or a vocabulary.
**Answer:** Take a position. Most multi-agent systems are one agent with extra latency and an ambiguous failure mode, and the test for whether separation is justified is whether failure modes, scaling profiles or deploy cadences genuinely differ. Then S01 as evidence that yours passes that test, including the cost you accepted (network boundaries, distributed failure model, tracing needed to debug one run).
**Follow-up trap:** *"You built one. Are you defending it?"* Say which agents you would merge (transcript processing and contextual chunking, since they always run in sequence on the same input) and which you would keep separate (gap detection, different trigger and cadence). Refusing to name a merge candidate reads as attachment to your own design and undercuts the whole answer.

### Q12 — Any company: why are you interviewing?
**Testing:** coherence, and whether you will leave them for the same reason.
**Answer:** Forward-looking, structural, specific. Never criticise Cornerstone; you built a platform for 2M+ users there and disparaging it devalues your own stories. `[CONFIRM: two sentences, written out.]`
**Follow-up trap:** *"Why this company specifically?"* Generic answers are worse than short ones. One concrete technical reason tied to something you have actually built beats three paragraphs of enthusiasm: for a lab, the inference and evaluation problems; for Microsoft, enterprise multi-tenancy at a scale your current estate does not reach. Interviewers discount enthusiasm and weight specificity.

---

## Red flags that fail you

- Naming a Leadership Principle explicitly while telling the story. Exhibit the behaviour; do not narrate the rubric.
- Vague, untranscribable answers at Google. The committee never met you.
- Team-scoped stories at Meta E6 presented as org-scoped.
- Not knowing your own weakest earlier answer before Microsoft's AA round.
- Over-structured STAR at Netflix or at a startup.
- Leading with engagement metrics at an infrastructure or lab role.
- Having no answer on AI-assisted coding in 2026.
- Inflating scope. It collapses on "which teams, and what did they want?"
- Fabricating a number in front of a Bar Raiser. The ~25% figure is your most attackable claim.
- Reciting a company's mission statement as evidence of alignment.
- Having no arguable technical opinion at an AI lab.
- Criticising your current employer anywhere.
- Assuming the published loop structure applies to your loop. Ask the recruiter.
- Bringing zero cost awareness to a GPU-adjacent role.

---

## Cheat card

```
AMAZON     16 LPs · 4-5 rounds (7-8 at Principal) · 2-3 LPs per interviewer
           BAR RAISER: outside team, VETO, drills until something breaks
           heaviest in practice: Dive Deep · Deliver Results · Invent+Simplify
                                 · Bias for Action
           Principal tenets: "Deliver Results is a LOW BAR"; clarity from
           complexity, hands-on, educates the org
           LEAD: S10 platform · S04 OOM · S13 -3,447 Java · S06 authz · S28 89%
           GAPS: Hire and Develop the Best · Earth's Best Employer  ← WRITE THESE
           RISK: the ~25% number. Prepare the measurement method FIRST.

GOOGLE     RRK · GCA · Leadership · GOOGLEYNESS (intellectual humility)
           HIRING COMMITTEE never met you, scores WRITTEN evidence
           → if it doesn't transcribe, it doesn't count
           L6: often 2 design rounds + tech leadership + 1-2 coding
           LEAD: S04 OOM · S02/S03 skill resolution · S11 humility · S24 · S14
           TACTIC: complete sentences · odd numbers (54,486 / 3,447 / 307)
                   announce your reasoning structure out loud

META       "Jedi" behavioural 45min: ownership, conflict, ambiguity, MISTAKES
           E6 onsite: coding + AI-ASSISTED CODING + architecture + design + behav
           + Leadership Assessment BEFORE onsite (replaces phone screen at E6)
           E6 bar: disagreement across 2+ TEAMS · impact on the ORG not team
           LEAD: S10 (60s, end on the merge critique) · S19 fleet · S11 · S21 · S29
           MUST HAVE: the AI-assisted coding answer
           RISK: single-team scope

MICROSOFT  competencies across rounds → "AS APPROPRIATE" round tailored to
           YOUR GAPS (interviewers sync notes first)
           relaxed AA = sell mode · aggressive AA = borderline
           growth mindset is a REAL rubric item ("learn-it-all")
           best fit on this list: multi-tenancy, global readiness, migration
           LEAD: S05 22 locales · S06 authz · S13 migration · S02 · S11
           TACTIC: track your weakest answer between rounds

NETFLIX    conversational · OFTEN NO WHITEBOARD · ~7 interviews
           keeper test + written culture memo = the rubric
           candour, context over control, high talent density
           LEAD: S11+S10 candid · S15 vLLM · S06 · S28 · S25 attribution gap
           TACTIC: verbal architecture (number components, state direction)
                   keep talking through silence · disagree once, well

AI LABS    OpenAI: recruiter → skills assessment → GATE-format screen (one
           problem, ~4 escalating stages) → PAID 48h WORK TRIAL → loop of 4-6
           Anthropic: 5 stages / 4-6 wks · 60min screen · take-home ·
           4-level coding: implement then REFACTOR as constraints are added
           high bar on WRITTEN reasoning · safety-serious, not doomer
           LEAD: S15/S16 vLLM+KV cache · S01 A2A/MCP · S23 rate limiting ·
                 S08 eval of a non-deterministic system · S04 OOM
           GAPS: no cost model · thin eval story · no public artifact
           SWAP METRICS: throughput/cost/p99, NOT ~25% engagement
           PREP GOES TO THE WORK TRIAL, not the behavioural round

UNIVERSAL  ask the recruiter what the rounds actually are
           two metric sets: product version vs systems version
           never criticise Cornerstone · never invent a number
           one arguable technical opinion, defensible
```

## Sources

- [Amazon's 16 Leadership Principles: Interview Guide (2026) — Exponent](https://www.tryexponent.com/blog/amazon-leadership-principles-interview) — accessed 2026-07-26
- [Amazon Leadership Principles: Resume Application, Interview Probe, Bar Raiser Read (2026) — ResumeAdapter](https://www.resumeadapter.com/companies/amazon/leadership-principles) — accessed 2026-07-26
- [Amazon Principal Engineering Tenets — Muktesh Mishra](https://mukteshkrmishra.medium.com/amazon-principal-engineering-tenets-947a00cc7233) — accessed 2026-07-26
- [Amazon Principal Engineer Interview Experience & Questions — Glassdoor](https://www.glassdoor.com/Interview/Amazon-Principal-Engineer-Interview-Questions-EI_IE6036.0,6_KO7,25.htm) — accessed 2026-07-26
- [Learnings from conducting ~1,000 interviews at Amazon — The Pragmatic Engineer](https://newsletter.pragmaticengineer.com/p/learnings-from-conducting-1000-interviews) — accessed 2026-07-26
- [Google Interview Process 2026: Loop & Committee — ResumeAdapter](https://www.resumeadapter.com/companies/google/interview-process) — accessed 2026-07-26
- [Google L6 Interview Guides & Questions (2026) — Hello Interview](https://www.hellointerview.com/guides/google/l6) — accessed 2026-07-26
- [Google's Googleyness & Leadership Interview Guide — Prepfully](https://prepfully.com/interview-guides/googles-googleyness-interview) — accessed 2026-07-26
- [Inside the Google 2026 Loop: Rounds, Rubric, and What Each Interviewer Scores You On — DGLearning](https://dglearning.substack.com/p/inside-the-google-2026-loop-rounds) — accessed 2026-07-26
- [Meta Interview Process 2026: Rounds, AI-Assisted Coding & Behavioral Rubric Explained — ClavePrep](https://claveprep.com/blog/meta-interview-process-2026-guide) — accessed 2026-07-26
- [Inside the Meta 2026 Loop: Rounds, Rubric, and What Each Interviewer Scores You On — DGLearning](https://dglearning.substack.com/p/inside-the-meta-2026-loop-rounds) — accessed 2026-07-26
- [Meta's Interview Loop Structure: Team Matching and Staff Engineer Screens — The Behavioral](https://thebehavioral.substack.com/p/metas-interview-loop-structure-team) — accessed 2026-07-26
- [Microsoft Interview Process 2026: AA Loop, Questions & Timeline — OphyAI](https://ophyai.com/blog/company-guides/microsoft-interview-guide) — accessed 2026-07-26
- [Microsoft L63-64 Interview Guides & Questions (2026) — Hello Interview](https://www.hellointerview.com/guides/microsoft/senior) — accessed 2026-07-26
- [Netflix Interview Process 2026: The Keeper Test, Culture Deck & How to Get Hired — ClavePrep](https://claveprep.com/blog/netflix-interview-process-2026-keeper-test-culture-deck) — accessed 2026-07-26
- [Netflix System Design Interview (2026 Guide) — Exponent](https://www.tryexponent.com/blog/netflix-system-design-interview) — accessed 2026-07-26
- [OpenAI Interview Process: 6 Stages Explained (2026) — Interview Coder](https://www.interviewcoder.co/blog/openai-interview-process) — accessed 2026-07-26
- [OpenAI Interview Process 2026: Team-by-Team Variation — techinterview](https://www.techinterview.org/post/3233474915/openai-interview-process-2026-team-by-team/) — accessed 2026-07-26
- [Anthropic Applied AI Engineer Interview Process: What the Top Frontier Lab Actually Tests in 2026 — Perspective AI](https://getperspective.ai/blog/anthropic-applied-ai-engineer-interview-process-frontier-lab-2026) — accessed 2026-07-26
- [Anthropic Interview Process & Timeline: 6 Steps to an Offer — IGotAnOffer](https://igotanoffer.com/en/advice/anthropic-interview-process) — accessed 2026-07-26

## Changelog
- 2026-07-26 — created
