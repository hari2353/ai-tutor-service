# The 45-Minute System Design Communication Framework

> **Track:** T14 Behavioral & Principal · **Time:** 1.5h · **Prereqs:** T10-distributed-fundamentals, T10-estimation · **Updated:** 2026-07-26
> **Module id:** `T14-design-communication` · **Tags:** sprint, behavioral, critical

## The 30-second version

A 45-minute design round is a time-allocation problem before it is a technical one, and the allocation is asymmetric: about 5 minutes on requirements, 3 on estimation, 12 to 15 on high-level design, 15 to 20 on deep dives, and 3 to 5 on close, because after reviewing rubrics at multiple FAANG-tier companies the reported pattern is that **deep-dive weight dominates everything else while most candidates spend 60% of their time on the high-level diagram** ([DesignGurus, 45-minute framework](https://designgurus.substack.com/p/how-to-design-any-system-in-45-minutes) — accessed 2026-07-26). Senior engineers fail this round on communication rather than knowledge: naming technologies in rapid succession without grounding them in the specific problem reads as performing knowledge rather than applying it, and describing components without ever discussing tradeoffs is the single most common gap ([Deep Engineering, why senior engineers fail](https://deepengineering.substack.com/p/why-senior-engineers-fail-system-design-interviews) — accessed 2026-07-26). At staff and above you are expected to **drive** rather than be driven, which in practice means you set the agenda out loud, you announce what you are skipping, and you offer the interviewer a choice of depth instead of waiting to be steered. The recoverable mistake is a wrong turn caught and named; the unrecoverable one is defending a design after the interviewer has told you twice that it will not work.

## Why this gets asked

Because the design round is the closest available proxy for what the job is: a room with an ambiguous problem, incomplete information, and other engineers who need to follow your reasoning well enough to disagree with it. The interviewer has sat through a real design review where a technically strong engineer could not be followed, so the meeting produced no decision and had to be run again. That is the failure this round is calibrated to detect. Concretely they are scoring four things simultaneously: whether you scope the problem yourself, whether you can be followed by someone who does not already know your answer, whether you state tradeoffs rather than only choices, and whether you notice and correct your own errors. At staff and above the reported bar shifts again: explaining the basics of every decision is actively penalised, since your interviewer is a staff-plus engineer who already knows most of what you would explain ([Hello Interview, staff-level system design](https://www.hellointerview.com/blog/staff-level-system-design) — accessed 2026-07-26). The senior failure mode is not knowing too little, it is calibrating the level of explanation wrongly in both directions at once.

---

## Lineage: past → present → future

**What came before.** Design interviews in the 2000s were largely unstructured architecture chats: the interviewer described a product, the candidate drew boxes, and the evaluation was "did this feel like someone I want in a design review". The pain that killed it was inconsistency, since two interviewers scoring the same candidate could not agree, and the strongest predictor of the outcome was how much the interviewer's own mental architecture matched the candidate's. The first correction was the arrival of a shared vocabulary: Nygard's *Release It!* (2007) gave failure patterns names, Kleppmann's *Designing Data-Intensive Applications* (2017) gave a shared reference for consistency and replication, and the "grokking" and ByteByteGo era (2018 onward) produced an explicit four-step framework, roughly clarify, high-level, deep dive, wrap up, which is now what most candidates arrive having memorised.

**Where it stands now.** The framework is universal and therefore no longer differentiating, which has moved the discriminating signal to two places. First, **time allocation**, because everyone knows the four steps and most people still spend the majority of the round on step two. Second, **whether the candidate drives**. At senior and above the interviewer expects to be a participant rather than a chair, and a candidate waiting to be asked the next question is being scored as needing management. The live disagreement in the field is about how prescriptive the framework should be: one camp teaches a rigid script with minute markers, and the other argues that a script produces candidates who follow the script through an interviewer's explicit redirection, which is worse than no script. The reconciliation most practitioners actually use is that the script governs your *defaults* and the interviewer's signals always override it. A second live disagreement is about diagrams: Netflix and some staff loops run entirely conversationally with no shared whiteboard, and multiple candidates report completing design rounds with no diagramming tool at all ([Exponent, Netflix system design 2026](https://www.tryexponent.com/blog/netflix-system-design-interview) — accessed 2026-07-26), which means diagram-dependent communication is a single point of failure you should not have.

**Where it's heading.** Three directions. High confidence: **more AI-system design, less CRUD-at-scale**. Meta already runs an AI-assisted coding round at E6 and the stated intent is to see whether you can direct work including machine-generated work ([ClavePrep, Meta 2026](https://claveprep.com/blog/meta-interview-process-2026-guide) — accessed 2026-07-26), and design rounds are following: expect retrieval, serving, cost per request and evaluation to appear as first-class design concerns rather than as an optional ML round. Medium confidence: **cost becomes a scored axis**. Designs that are correct and unaffordable are increasingly marked down, particularly anywhere GPU capacity is involved, which favours candidates who can derive a cost envelope out loud. Speculative: **the AI-pair design round**, where you design with an assistant in the room and the evaluation is your judgment about what to accept, override and verify. Prototypes of this exist in coding rounds; treat its arrival in design as a plausible direction rather than a plan.

---

## Mental model

The round is a **budget you spend down, out loud**. Everything you say is either buying information, buying agreement, or buying depth, and running out of budget with no depth spent is the standard failure.

```
 0                    10                   20                   30                   40   45
 ├────────┬─────┬─────────────────────────┬──────────────────────────────────┬────────┤
 │ FRAME  │ EST │   HIGH-LEVEL DESIGN     │        DEEP DIVES                │ CLOSE  │
 │ 0-5    │ 5-8 │        8-22             │          22-40                   │ 40-45  │
 └────────┴─────┴─────────────────────────┴──────────────────────────────────┴────────┘
   ask       do    draw the whole thing      go two levels down on 2, maybe 3   summarise
   scope     the   end to end, breadth       things. THIS IS WHERE THE          + name what
   + write   math  first, no depth yet       SCORE IS.                          you'd do
   it down                                                                      next

 What candidates actually do:
 ├──────────────────┬────────────────────────────────────────────┬─────────────┬──┤
 │ FRAME 0-10       │ HIGH-LEVEL 10-35 (adding boxes, no depth)  │ DEEP 35-43  │? │
 └──────────────────┴────────────────────────────────────────────┴─────────────┴──┘
                                                                   ↑
                                        8 minutes of the only part that scores heavily
```

The second half of the model is what the interviewer is holding in their head, which is not your diagram. It is a scorecard with roughly four axes, and every sentence you say lands on one of them:

```
   ┌─────────────────────┬──────────────────────────────────────────────┐
   │ SCOPING             │ did they define the problem, or wait for it? │
   │ COMMUNICATION       │ could I follow it without knowing the answer?│
   │ TECHNICAL DEPTH     │ did they go below the name of the technology? │
   │ TRADEOFFS/JUDGMENT  │ did they choose, or just list?               │
   └─────────────────────┴──────────────────────────────────────────────┘

   Failure asymmetry: you can pass with a mediocre architecture and
   excellent reasoning. You cannot pass with an excellent architecture
   and reasoning the interviewer could not follow.
```

**The one-sentence version of the whole module:** narrate your decisions, not your knowledge.

---

## How it actually works

### Minute by minute

The times are defaults. The interviewer's signals override them every time, and knowing the default is what lets you notice when you are behind.

---

#### 0:00 to 0:02 — Restate and take control

Do not start drawing. Do not start listing technologies. Restate the problem in one sentence, then declare your plan.

> "So we're designing a system that lets 2 million enterprise users get personalised content recommendations, multi-tenant. Before I design anything I want to spend about four minutes on requirements and scope, then do some quick estimation, then sketch the whole thing end to end, and then go deep wherever you think is most useful. Does that work?"

Three things that sentence does. It confirms you understood the problem, which is cheap insurance against designing the wrong thing for 40 minutes. It sets an agenda, which is the first and easiest seniority signal available. And it ends with a question, which makes the round collaborative from minute two.

**What not to do:** "OK so I'd probably use Kafka and a vector database and..." Naming technology in the first thirty seconds is the strongest juniority signal in the entire round, because it means you pattern-matched the prompt to a template rather than thinking about the problem.

---

#### 0:02 to 0:05 — Requirements, in a fixed order

Ask in this order, because it is the order the answers depend on each other.

1. **Users and scale.** "Who uses this and roughly how many? Are they consumers or enterprise tenants?" Scale changes architecture; everything else is downstream.
2. **The two or three core features.** "I'm going to assume the core is: request recommendations, ingest interaction events, and search. Is there anything critical I'm missing?" Propose, then let them correct. Asking "what are the requirements?" makes them do your job.
3. **The dominant non-functional constraint.** "Which of these matters most: latency, consistency, availability, or cost?" This is the single highest-value question in the round, because it decides most of your tradeoffs and you can refer back to their answer every time you make one.
4. **Explicit non-goals.** "I'm going to treat authentication, billing and the content authoring workflow as out of scope. Fair?"

Write these on the board in a corner and leave them there. You will point at them later, which is worth more than the writing.

**Ask three or four questions, not ten.** More than about four minutes on clarification and the interviewer starts wondering whether you can make a decision. The rule for whether a question is worth asking: **would a different answer change your architecture?** "How many users?" changes it. "What's the exact SLA in milliseconds?" usually does not, because you are going to design for a target and state it. Ask the first, assume the second and say your assumption out loud.

> **Signal phrase:** "Rather than ask you every detail, I'll state my assumptions as I go and you can correct me."

---

#### 0:05 to 0:08 — Estimation, out loud, with round numbers

Three minutes, and the point is not the number, it is that you can derive load rather than guess it.

> "2 million users. If 10% are daily active that's 200,000 DAU. Say 5 recommendation-bearing page views each, so a million requests a day. A million over 86,400 seconds is roughly 12 requests per second average, and with a working-hours peak I'd plan for 5 to 10 times that, so call it 100 rps peak. That's small. The interesting number is that each request hydrates around 100 content items, so uncached that's 10,000 downstream calls a second, which tells me the caching layer is not optional and is probably where the design lives."

Notice what that does: it ends by identifying **where the design problem actually is**. Estimation whose output is a number is a calculation; estimation whose output is a design constraint is engineering.

Use powers of ten, round aggressively, and say the assumption before the arithmetic. If you get the arithmetic wrong and catch it, say so and move on; nobody scores the multiplication.

**Storage and bandwidth follow the same pattern.** For a vector system: "1.2 million rows at 512 dimensions, float32, so 1.2M × 512 × 4 bytes, about 2.5 gigabytes. That fits in memory on one node, which means I do not need a distributed vector store and I should say why I am not using one."

---

#### 0:08 to 0:22 — High-level design: breadth first, no depth

Draw the whole system end to end before going deep on any part. The discipline is hard and it is the difference between a design and a fragment.

**Order of drawing:**
1. The client and the entry point.
2. The write path, all the way to storage.
3. The read path, all the way to the response.
4. The batch or async path if there is one.
5. Only then, name technologies for each box.

**Narrate as you draw, in decisions:**

> "Requests come into a service that resolves tenant and user, then fans out in parallel, not sequentially, to user context and candidate retrieval, because serialising them adds their latencies instead of taking the max. Retrieval hits a vector index. Then scoring, then hydration of the content metadata, which is where the cache goes."

Say "in parallel, not sequentially, because" out loud. That clause is a tradeoff statement embedded in a description and it is exactly what the rubric is looking for.

**Box budget: nine.** More than nine boxes and the diagram becomes unreadable and you have started drawing deployment topology instead of data flow. If you need more detail, that is what the deep dive is for.

**Announce your skips.** "I'm drawing the event ingestion path as one box for now; I know there's a queue and a consumer group in there and I'll expand it if we go that way." This is a strong signal because it proves the omission was a choice.

**At about 20 minutes, checkpoint deliberately:**

> "That's the whole system end to end. I think the two most interesting problems here are multi-tenant isolation in the shared vector index, and the hydration fan-out. I'd start with the fan-out because I think it's the actual bottleneck. Would you rather I go there, or somewhere else?"

That sentence does four things: it declares breadth complete, it demonstrates prioritisation by naming what is interesting and why, it makes a recommendation rather than only offering a menu, and it hands over control briefly. Offering a menu with no recommendation is a weaker version of the same move.

---

#### 0:22 to 0:40 — Deep dives: the part that scores

This is 40% of the round and it is where the decision is made. Two topics done properly beats five touched.

**The structure of one deep dive, roughly 6 to 8 minutes:**

```
1. Name the problem precisely          "100+ metadata lookups per request
                                        against an external API"
2. State the constraint                "external p99 is ~X, and it's also the
                                        availability ceiling for our path"
3. Give the option space (2-3 real)    "in-process cache, distributed cache,
                                        or ask them for a bulk endpoint"
4. Choose, with the reason             "distributed, because with N replicas
                                        in-process gives N× the misses and
                                        evaporates on every deploy"
5. State the cost you accept           "it's a consistency compromise and
                                        another system in the path"
6. Go one level below the choice       "keyed per content id so hydration is
                                        a multi-get with a small miss set"
7. Volunteer the failure mode          "the real risk is a thundering herd
                                        when a hot key expires: jittered TTLs,
                                        single-flight per key, and
                                        stale-while-revalidate"
```

Step 7 is the one that separates staff from senior, and it is unprompted. Volunteering the failure mode of your own solution before being asked is the highest-value habit in the entire round.

**Depth means below the name of the technology.** "I'd use HNSW" is a name. "HNSW is a navigable small-world graph with a hierarchy of layers, so search descends from a sparse top layer to a dense bottom one; the knobs are `M`, which is the graph degree, and `efSearch`, which trades recall for latency at query time, and the reason filtered search is hard is that pre-filtering breaks the graph's connectivity assumptions while post-filtering makes you over-fetch by the inverse of the selectivity" is depth. Have two or three technologies you can do this for; you do not need it for everything.

**Do not explain what the interviewer already knows.** At staff level, explaining what a load balancer does is actively negative. Calibrate by watching them: if they are nodding along and not writing, you are at the wrong altitude, so go down a level. The move is to compress the known part and expand the specific part: "you know how a cache works, so let me go straight to the invalidation question, which is where this one is interesting."

---

#### 0:40 to 0:45 — Close

Do not let the round end by running out of clock. At 40 minutes, close deliberately.

> "Let me summarise. We've got a fan-out read path with a distributed cache handling the metadata hydration, which was the bottleneck the estimation pointed at, a shared vector index with tenant as a filter and a prefix of the sort key so it prunes rather than post-filters, and an async event path that's isolated from serving so ingestion load can't degrade read latency. The two things I'd want to fix before shipping are the thundering-herd behaviour on hot cache keys, and the fact that I have no story yet for how a tenant with only 50 items gets sensible results, since ANN is the wrong algorithm at that size and it should fall back to an exact scan. If I had more time the next thing I'd design is the evaluation path, because right now nothing tells us whether recommendations are getting better."

Four elements: what you built, why the key decision was made, what you know is unfinished, and what you would do next. Naming your own gaps at the close is not weakness; it is the last and cheapest opportunity to demonstrate calibration, and interviewers write it down.

---

### The phrase bank

This is the operational core of the module. Phrasing is not decoration; the interviewer is transcribing quotable sentences for a written packet, and at Google specifically a hiring committee that never met you scores that packet ([ResumeAdapter, Google 2026](https://www.resumeadapter.com/companies/google/interview-process) — accessed 2026-07-26). Which words you use is literally the artifact.

#### Phrases that signal seniority

**Setting the agenda**
- "Before I design anything, I want to spend four minutes on requirements."
- "I'll state my assumptions as I go rather than asking you every detail."
- "Let me draw the whole thing end to end first, then go deep where it matters."
- "I'm going to skip X for now and come back if it's load-bearing."

**Signalling a tradeoff, which is the highest-value category**
- "There are three reasonable options here. Let me name them and say which I'd pick and why."
- "I'm choosing X over Y. The cost I'm accepting is Z."
- "That buys us consistency and costs us availability during a partition. Given you said latency matters most, I'd take the other side."
- "This is the wrong choice if the read-write ratio inverts. Let me say what would make me change it."
- "I'd want to measure that before committing. The number that would decide it is ___."

**Signalling depth without lecturing**
- "You know how a cache works, so let me go straight to the invalidation question."
- "One level down: the knob that actually matters here is ___."
- "The reason this is hard is not the algorithm, it's that the filter interacts badly with the index."

**Volunteering failure, the strongest single habit**
- "The failure mode of what I just described is ___, and here's how I'd handle it."
- "What would break first at 10x is ___, and the symptom would be ___ rather than an error."
- "This is silent when it fails, which is what worries me about it."
- "I'd want an alarm on ___ specifically, because otherwise this degrades without anyone noticing."

**Scoping and prioritising**
- "That's a real problem and I don't think it's the biggest one here. The biggest one is ___."
- "I'd ship this without X, and here's what X buys us and when I'd add it."
- "There are two ways to spend the next ten minutes. I'd rather go deep on ___. Your call."

**Recovering cleanly**
- "I've changed my mind on that. Here's why, and here's what I'd do instead."
- "Let me back up. I think I optimised the wrong thing."
- "You're right, that doesn't work. The reason it doesn't is ___, which means I need ___."

**Handling the unknown**
- "I don't know that. Here's how I'd find out, and here's what I'd assume in the meantime."
- "I've not used that in production. What I know about it is ___, and here's the analogous thing I have used."

**Cost and operations, increasingly scored**
- "Roughly what does this cost per month? Let me get to an order of magnitude."
- "The on-call burden of this is ___, which is a real argument against it."
- "This is correct and I'm not sure it's affordable. Let me size it."

#### Phrases that signal juniority

Each of these has a specific reason, and the reason matters more than the phrase.

| Phrase | Why it hurts | Say instead |
|---|---|---|
| "I'd use Kafka and Redis and a vector DB..." in the first minute | Pattern-matched the prompt instead of thinking about the problem | "Let me understand the constraints first, then pick components." |
| "It depends." (full stop) | Correct and useless. The information is in what it depends on. | "It depends on the read-write ratio. If reads dominate, X; if writes, Y." |
| "What are the requirements?" | Asks the interviewer to do your job | "I'll assume A, B and C are the core. Anything critical missing?" |
| "This is best practice." | Appeals to authority instead of reasoning. Also often untrue in context. | "I'd choose this because, in this specific case, ___." |
| "We'd just add a cache." / "We'd just scale horizontally." | "Just" always hides the hard part. Also skips invalidation, coherence, and cost. | "A cache helps here; the hard part is invalidation, so ___." |
| "Obviously we'd shard by user ID." | Nothing is obvious. Also skips the skew question. | "I'd shard on user id, accepting that a very large tenant creates a hot partition, which I'd handle with a composite key." |
| "Microservices." (as an answer) | Names an org pattern instead of a decomposition criterion | "I'd split on independent scaling and failure. Concretely, these two profiles diverge because ___." |
| "I'd use MongoDB because it's scalable." | Category error. Adjective in place of a property. | "Document model fits because the access pattern is one read per user profile with no cross-entity joins." |
| "Let me use the CAP theorem here. We need CP." | CAP describes behaviour only during a partition, and "pick two of three" is the classic wrong answer | "Partition-free, this is a latency-versus-consistency choice, which is the PACELC framing. During a partition I'd ___." |
| "That's an edge case." | Dismisses instead of scoping. Interviewers often ask because it is not one. | "That's rare enough that I'd handle it with ___ rather than designing around it, unless it's more common than I think." |
| "I've not done that, so I can't say." | Ends the thread. The interviewer wanted your reasoning, not your CV. | "I've not run that in production. Here's what I know about it and here's the analogous thing I have run." |
| "It should work." | Hope, not analysis | "Here's what would make it fail, and here's the mitigation." |
| "We can optimise later." | Sometimes right, but as a reflex it dodges the question | "I'd defer this optimisation because the estimation says it's not the bottleneck. The bottleneck is ___." |
| Long silence while thinking | Unscoreable. Silence is the only thing worse than a wrong answer. | "Let me think out loud for a second. The options I see are..." |
| "Does that make sense?" repeatedly | Reads as needing reassurance | "I'll pause there. Anything you want me to expand?" |
| "As I mentioned..." when correcting yourself | Defends a position you are abandoning | "I've changed my mind on that." |
| "The system will handle it." | Passive voice hides the mechanism, which is the whole question | "The queue handles it by ___." |
| Naming a paper or a company as the argument | "Google does it this way" is not a reason, and their constraints are not yours | "The approach in ___ applies here because our constraint is the same; where it differs is ___." |

**The single most damaging pattern is not a phrase, it is jargon density.** Naming technologies and concepts in rapid succession without grounding them in the specific problem reads as performing knowledge rather than applying it, and experienced interviewers recognise it immediately. The countermeasure is a rule: **every technology you name must be followed by a "because" tied to this problem within one sentence.** No orphan nouns.

---

### How to signal tradeoff thinking without slowing down

The mechanical pattern, usable in about eight seconds:

```
"<option A> or <option B>. I'd take <A>, because <property of THIS problem>.
 What I'm giving up is <cost>."
```

Examples you can say at speed:

- "Strong or eventual consistency on the profile read. I'd take eventual, because a recommendation computed from a five-second-old profile is fine and a synchronous cross-region read is not. What I'm giving up is that a user who just updated their skills might not see it reflected on the next page load, which I'd fix with a read-your-writes session guarantee rather than global strong consistency."
- "Cache in-process or distributed. Distributed, because with a dozen replicas in-process gives twelve times the misses and evaporates on every deploy. What I'm giving up is a network hop per lookup and another system in the path."
- "One vector index with a tenant filter, or an index per tenant. One with a filter, because per-tenant indices multiply operational surface and the small tenants would each have too few vectors for a well-connected graph. What I'm giving up is that I now have to make sure the filter prunes rather than post-filters, which is a table-definition problem."

**Volunteer the counter-argument once per deep dive.** "The argument for the other side is ___, and it would win if ___." This is the clearest available evidence that you chose rather than defaulted, and it costs ten seconds.

---

### Handling "how would you scale this"

This question arrives in every round and it has a wrong answer that most people give, which is to list scaling techniques.

**The wrong answer:** "I'd add caching, shard the database, add read replicas, put a CDN in front, and autoscale the service tier."

**Why it is wrong:** it does not identify the binding constraint, so it demonstrates vocabulary rather than analysis. Every one of those techniques is correct for some system and irrelevant for this one.

**The right shape, four steps:**

1. **Ask what is scaling.** "10x users, 10x data, or 10x requests per user? They break different things." This is a legitimate clarifying question and asking it is itself a signal.
2. **Name the component that breaks first, and why.** "The reranker. It runs a cross-encoder over the candidate list, so its cost is linear in candidates times QPS, it cannot be precomputed, and it's already the dominant latency term."
3. **Name the symptom, not just the cause.** "What I'd see first is p99 growing while error rate stays flat, and queue time growing faster than compute time. Not an error, just slow, which is why I'd want an alarm on queue time separately from total latency."
4. **Then give the fix, and the next thing that breaks.** "I'd cut candidates into the reranker, batch across requests, and consider distilling to a smaller cross-encoder. Once that's fixed the next constraint is the vector index memory, at which point I'd shard by tenant, which is clean because tenant is already the query scope."

Step 3 is the one almost nobody does, and it is the one that proves you have operated a system rather than only designed one.

**Have the 100x answer ready too, and make it qualitatively different.** At 10x you tune and shard; at 100x the architecture assumptions break and you say which ones. Giving the same list at both scales is a junior tell.

---

### How to recover from a wrong turn

Wrong turns are expected and are not disqualifying. How you exit one is scored directly, and it is one of the few places where a mistake can improve your outcome.

**Recognising it.** Three signals, in escalating order of urgency:
1. The interviewer asks the same question a second time in different words. They are not curious, they are steering.
2. "Are you sure that works?" or "Walk me through what happens when..." This is a hint, not a question.
3. They go quiet and stop writing.

**The recovery script:**

```
1. STOP. Do not finish the sentence you were on.
2. NAME IT.        "Let me back up. I don't think that works."
3. SAY WHY.        "The problem is that a per-executor rate limit
                    multiplies by executor count, so twenty executors
                    at ten in flight is two hundred."
4. GIVE THE FIX.   "So the budget has to be global, which means a
                    shared counter, which is a distributed rate limiter."
5. NAME THE NEW COST. "And that has its own failure mode: if the
                    counter is unavailable I have to choose between
                    failing closed and failing open."
6. MOVE ON. Do not apologise more than once, and do not relitigate.
```

**Why step 3 matters most.** "You're right, let me change it" scores as compliance. "You're right, and the reason it doesn't work is X" scores as understanding. The interviewer cannot tell whether you actually understood the correction unless you articulate the failure yourself.

**Do not defend past the second signal.** The single fastest way to fail this round is to argue for a design after the interviewer has told you twice it will not work. It reads as unable to take input, which is disqualifying at any level and especially at staff-plus where the job is largely absorbing input from people who know things you do not.

**But do not fold on the first push either.** Interviewers sometimes push on a correct decision to see whether you understand it or merely asserted it. The distinction: if they present *new information* ("what if the write rate is 100x the read rate"), update. If they only apply *pressure* ("are you sure?"), restate your reasoning once, with the condition that would change your mind: "I'd still take this, because ___. What would change my mind is if ___." Then, if they push again, take it seriously. Holding a correct position once with stated reasoning, then updating when given a reason, is the ideal sequence.

**If you are lost and there is no obvious exit:** "I've talked myself into a corner. Let me go back to the requirement, which was ___, and re-approach from there." Returning to the written requirements in the corner of the board is exactly why you wrote them down.

---

### The no-whiteboard case

Some staff-level rounds, Netflix's among them, run entirely conversationally with no shared diagramming tool, and multiple candidates report completing the round without any. Diagram-dependent communication is therefore a single point of failure.

**Verbal architecture technique.** Numbered components and explicit direction:

> "There are four components. One, an edge service that resolves tenant and user. Two, a context service holding the user's features. Three, a retrieval service over a vector index. Four, a scoring service. The request goes edge, then fans out in parallel to two and three, and both results go into four. Separately, and asynchronously, an event processor writes into the same store that two reads from, so ingestion and serving are decoupled. I'll refer to them as edge, context, retrieval and scoring from here."

Three techniques doing the work: number the components so you can reference them without re-describing them, state direction explicitly since there is no arrow, and name the components once so both of you use the same vocabulary. Then check in: "does that structure make sense before I go into the retrieval path?"

**Practise this.** Run through System 2 from the resume-systems module with your hands behind your back. If you cannot do it verbally, you are one broken screen-share away from a bad round.

---

## Practical exercise (replaces "Build it from scratch")

No implementation. About 90 minutes, timed, out loud. Recording yourself is not optional; the defects this module describes are inaudible from the inside.

**Block 1 (10 min) — The opening, ten times.** Say the 0:00 to 0:02 opening for ten different prompts (design a rate limiter, a notification service, a RAG system at 10M documents, a feature store, a multi-tenant vector search, an LLM gateway, a recommendation platform, an agent orchestration platform, a metrics pipeline, a URL shortener). Same structure every time: restate, declare the plan, ask for agreement. Target 25 seconds. This must become automatic, because the first thirty seconds set the frame for the entire round.

**Block 2 (15 min) — Estimation to constraint.** Five prompts, three minutes each. The requirement is that every estimation ends with a sentence of the form "which tells me the design problem is ___". A number with no conclusion is a failed drill.

**Block 3 (25 min) — Full 45-minute round, timed, recorded.** Pick a prompt you have not rehearsed. Set a visible timer with marks at 8, 22 and 40 minutes. Run it. Then listen back and count: how many technologies you named without a "because" in the same sentence, how many times you said "just", how long your requirements phase actually ran, and what minute you reached your first deep dive. Most people are surprised by the last one.

**Block 4 (15 min) — Tradeoff drill.** Twenty rapid-fire pairs, eight seconds each, using the template "A or B. I'd take A because [property of this problem]. What I'm giving up is C." Pairs: SQL/NoSQL · strong/eventual · sync/async · cache-aside/write-through · in-process/distributed cache · HNSW/IVF · monolith/services · self-host/API · batch/stream · pull/push · REST/gRPC · single-region/multi-region · optimistic/pessimistic locking · hash/range partitioning · client-side/server-side rendering · bi-encoder/cross-encoder · fine-tune/RAG · one index/index-per-tenant · retry/circuit-break · vertical/horizontal scaling.

**Block 5 (10 min) — Recovery drill.** Have someone (or an LLM playing the interviewer) tell you three times that a correct design is wrong. Practise both branches: hold once with stated reasoning when only pressure is applied, and update cleanly with the failure articulated in your own words when new information is given. The skill is telling those two situations apart in real time.

**Block 6 (15 min) — No-whiteboard run.** Describe one of your five flagship systems verbally, hands behind your back, numbered components, explicit directions. Time it at four minutes.

---

## How it's done in production

**What the interviewer is actually doing while you talk.** They are writing quotable evidence against a rubric, not evaluating your architecture against a reference solution. At Google that written packet is scored by a hiring committee who never met you, which means anything that does not survive transcription does not count: gestures, tone, and vague competence all evaporate. Specific quotable sentences ("said he'd shard by tenant and accept a hot partition for the largest tenant, handled by a composite key") survive. This is a direct argument for stating decisions in complete sentences rather than pointing at a diagram.

**Company variation in the same 45 minutes.**

| Company | What the design round emphasises | Adjustment |
|---|---|---|
| Amazon | Ownership and customer impact woven into a technical answer; LPs bleed into the design round | Say who the customer is and what breaks for them. Tie a decision to a customer outcome at least once. |
| Google | Structured reasoning and adaptability (GCA), quotable specifics for the committee | Announce your structure explicitly. Speak in complete, transcribable sentences. |
| Meta | Two design rounds at E6+ (architecture and product design), speed, practicality | Move faster. Meta rounds are dense; do not spend six minutes on requirements. |
| Microsoft | Depth in your actual domain, then an "As Appropriate" round tailored to earlier gaps | Assume the weakest thing you say gets revisited later in the loop. Note it and prepare the second pass. |
| Netflix | Conversational, domain-specific, often no whiteboard, senior-to-senior discussion | Practise verbal architecture. Expect to be treated as a peer, which means fewer prompts and more expectation that you drive. |
| AI startups | Practical, cost-aware, evaluation-aware; often about a system close to what they actually run | Bring cost per request and an evaluation story. Both are usually missing from candidates' designs. |

### Failure-mode table

| Symptom | Cause | Fix |
|---|---|---|
| Interviewer starts asking a rapid series of pointed questions | You stopped driving; they are now driving | Reassert: "Let me take stock. Here's what we have and here's what I think is left." |
| At 35 minutes you have not gone deep on anything | Too long on requirements or breadth | Hard timer at 22 minutes. When it hits, checkpoint and move regardless of whether the diagram feels finished. |
| "Can you be more specific?" | You are speaking in nouns instead of mechanisms | Every technology followed by a "because" tied to this problem, in the same sentence. |
| Interviewer repeats a question in different words | They are steering you off a wrong turn | Treat any repeat as a correction. Stop, name it, say why. |
| You explain something and they look bored | Wrong altitude, too basic | "You know this, so let me go to the part that's actually interesting here." |
| Ran out of time mid-sentence | No close planned | Close at 40 minutes regardless of state. An unfinished design closed well beats a finished one cut off. |
| Long silences | Thinking without narrating | "Let me think out loud. The options I see are..." Silence is unscoreable. |
| They ask about cost and you have nothing | Cost treated as someone else's problem | Have an order-of-magnitude method for every design. State assumptions, give a range. |
| Feedback says "strong technically, concerns about communication" | Jargon density; components described without tradeoffs | The no-orphan-nouns rule, plus one explicit tradeoff per deep dive with the counter-argument stated. |
| Feedback says "needed a lot of prompting" | Waited to be asked | Own the agenda at 0:02, checkpoint at 0:22, close at 0:40 without being invited to. |

---

## Tradeoffs & when NOT to use it

**When the script is wrong.**

- **When the interviewer explicitly redirects.** The framework governs your defaults and their signals always override. A candidate who continues to the next scripted phase through an explicit redirect is failing the round *because of* the preparation, which is the most avoidable failure mode there is.
- **In a 30-minute round.** Compress proportionally and cut estimation to 60 seconds, but never cut the deep dive. If time is short, do one deep dive properly and say "I'd normally also look at X" rather than two shallow ones.
- **When it is a resume deep dive, not a design exercise.** "Walk me through your recommendation platform" is a different round, covered in `T10-resume-systems`. There is no requirements phase because the requirements are historical facts. Applying the design script there makes you sound like you are inventing your own past work.
- **In a conversational round with no whiteboard.** The phases still apply; the diagram does not. Do not spend the round asking for a shared screen.
- **At an early-stage startup.** A founder often wants to know whether you can ship this quarter, and a candidate who spends five minutes on requirements for a system with 400 users reads as heavyweight. Compress framing hard, get concrete fast, and talk about what you would build first.
- **When you genuinely do not know the domain.** Do not fake a framework over a hollow middle. "I've not built a video pipeline. Let me reason from first principles and you can correct my assumptions" is a legitimate and sometimes strong answer, because reasoning under acknowledged ignorance is exactly what General Cognitive Ability measures.
- **Do not over-verbalise.** There is a failure mode on the other side: narrating every micro-thought is exhausting and lowers signal density. Narrate decisions and the reasoning behind them, not your entire stream of consciousness.
- **Do not perform humility either.** Volunteering failure modes is high value; hedging every statement is not. "I might be wrong but maybe we could possibly consider" is worse than a clear position you are willing to revise.

---

## Interview questions

Meta-questions about the round itself, which come up in prep conversations, debriefs and recruiter screens, plus the in-round questions whose *handling* is what is being scored.

### Q1 — How would you scale this?
**Testing:** whether you can identify a binding constraint or only list techniques.
**Answer:** Ask what is scaling (users, data, or requests per user). Name the component that breaks first and why it is that one. Name the observable symptom, not just the cause. Then the fix, then what breaks next.
**Follow-up trap:** *"And at 100x?"* The answer must be qualitatively different, not the same list with bigger numbers. At 10x you tune and shard; at 100x specific architectural assumptions break and you should name which. Repeating the 10x answer is the tell.

### Q2 — What would you do differently with a week instead of a quarter?
**Testing:** prioritisation, and whether you know which parts of your own design are load-bearing.
**Answer:** Name what you keep and what you cut, ordered by whether it is load-bearing for everything else. Measurement and the write path are usually load-bearing; the sophisticated ranking layer usually is not.
**Follow-up trap:** *"So the thing you cut was not important?"* No: deferrable is not unimportant. Say what it buys and the trigger that would make you build it. Conflating "cut first" with "unnecessary" is a reasoning error interviewers probe for.

### Q3 — Why did you choose that database?
**Testing:** whether you reason from access pattern or from familiarity.
**Answer:** From the access pattern and the consistency requirement, not from properties of the product. "One read per user profile keyed by id, no cross-entity joins, and the shape varies per tenant, so a document model fits and I do not need referential integrity here."
**Follow-up trap:** *"What would make you switch?"* Have a specific trigger: a join pattern appearing, a transactional requirement across entities, or an analytical query pattern that a document store serves badly. A choice with no switching condition was a preference.

### Q4 — What happens when [component] fails?
**Testing:** whether you designed for failure or only for the happy path.
**Answer:** Name the blast radius, the user-visible effect, and the degradation strategy in that order. "The metadata API failing means hydration fails, so cached items are served and misses fail. That degrades by hit rate, which is not a design, so I would add stale-while-revalidate with bounded staleness and a circuit breaker so the miss path fails fast rather than consuming the request budget."
**Follow-up trap:** *"What if two things fail at once?"* Do not enumerate combinatorics. Name the shared dependency, because correlated failure is the interesting case: "the meaningful pair is anything that shares the cache, since a cache failure turns every request into a cold path and the downstream sees 100x its normal load."

### Q5 — You have 30 seconds. What is the single most important design decision here?
**Testing:** whether you can rank your own decisions.
**Answer:** Pick one and say why it dominates. "Making event ingestion structurally unable to affect serving latency, because that is the failure that takes down the whole product rather than one feature."
**Follow-up trap:** *"Not the database choice?"* Explain why that one is reversible and yours is not. Reversibility is the right ranking axis for design decisions, and saying so explicitly is a strong senior signal.

### Q6 — I do not think that will work.
**Testing:** how you handle pressure, which is scored more heavily than the design itself.
**Answer:** Distinguish new information from pressure. If they gave you a reason, engage with the reason and update, articulating the failure in your own words. If they only applied pressure, restate your reasoning once and name what would change your mind.
**Follow-up trap:** *"I still don't think it works."* Now take it seriously regardless of whether they gave a reason. Ask directly: "what am I missing?" Asking is not weakness; continuing to defend past the second push is disqualifying.

### Q7 — How much would this cost to run?
**Testing:** cost literacy, which is increasingly a scored axis and is rare.
**Answer:** Derive to an order of magnitude with assumptions stated aloud. Instance count times hourly rate for compute, bytes times storage rate, and per-token or per-request for anything metered. Give a range and name the dominant line item.
**Follow-up trap:** *"Cut it in half."* Name the dominant line and attack it specifically, then name what quality or latency you give up. For GPU serving that is utilisation, model size, or moving eligible traffic to a batch path. Listing three levers without picking one is a weaker answer than picking one and stating its cost.

### Q8 — Which part of your design are you least confident about?
**Testing:** calibration, and whether you can criticise your own work in real time.
**Answer:** Name one specifically, with the reason and how you would resolve it. "The tenant-size distribution. My design assumes tenants are large enough that ANN is the right algorithm, and if most tenants have a few hundred items then exact search is both faster and exact, which changes the retrieval path."
**Follow-up trap:** *"So your design is wrong?"* No: it is conditional on an assumption you have named and would verify. Stating the assumption and the measurement that resolves it is the answer. Collapsing into "yes it's wrong" is as bad as refusing to name a weakness.

### Q9 — Could you do this with a single machine?
**Testing:** whether you over-engineer by default. This question is a trap and it is asked deliberately.
**Answer:** Often yes, and say so. "At 100 rps peak with 2.5 GB of vectors, a single well-provisioned instance handles this. I'd distribute for availability and deployment independence rather than for capacity, and it is worth being explicit about which of those is the actual reason."
**Follow-up trap:** *"Then why did you draw eight boxes?"* Have a real answer: independent scaling profiles, independent failure, or organisational boundaries. If the real reason is habit, say so. Candidates who cannot justify their own distribution are marked down for over-engineering, and this is one of the few questions where the humble answer is the strong one.

### Q10 — We are out of time. Summarise.
**Testing:** whether you can compress and whether you know what mattered.
**Answer:** Four beats in about 45 seconds: what you built, the key decision and its reason, what is unfinished, what you would do next.
**Follow-up trap:** *"What did we not get to that you wish we had?"* Name something specific and substantive, ideally the thing you flagged as your weakest point earlier. It shows you were tracking the shape of the round rather than just answering questions, and it is the last impression in the interviewer's notes.

### Q11 — Walk me through the request path, end to end, with numbers.
**Testing:** whether your design is real or a diagram.
**Answer:** Component by component with a latency figure and where it comes from. "Edge resolves tenant, single-digit ms. Parallel fan-out, so the cost is the max of context and retrieval, not the sum. Retrieval is ANN plus rerank, and rerank dominates. Hydration is a Redis multi-get plus the miss set. Total budget X, with the rerank as the largest term."
**Follow-up trap:** *"Where does the p99 come from, versus the p50?"* Almost always the tail of one dependency plus queueing, not the average of everything. Naming queueing specifically, and saying you would monitor queue time separately from service time, is the strong answer.

### Q12 — You have not mentioned monitoring at all.
**Testing:** whether operability is part of your design or an afterthought. Frequently asked precisely because candidates skip it.
**Answer:** Name the three or four signals that would actually detect your failure modes, not a generic list. "Queue time separately from total latency, cache hit rate, the rate of the silent-failure path (the fallback or unresolved counter), and cost per request. Those are the ones where a degradation is otherwise invisible."
**Follow-up trap:** *"What would you alert on, versus dashboard?"* Alert on things that require human action and are not self-healing; dashboard the rest. Then the sharper point: alert on symptoms users feel, such as error rate and latency SLO burn, rather than on causes such as CPU, because cause-based alerts page you for things that do not matter and miss things that do.

---

## Red flags that fail you

- Naming technologies in the first thirty seconds.
- Reaching 35 minutes with no deep dive.
- Describing components without a single stated tradeoff.
- Jargon in rapid succession with nothing tied to this problem. The clearest senior-fail pattern there is.
- Defending a design after the interviewer has pushed twice.
- Folding instantly on the first push, with no reasoning offered.
- "It depends" with no statement of what it depends on.
- "We'd just add a cache."
- Long silences instead of narrated thinking.
- Waiting to be asked what to do next, all round.
- Explaining what a load balancer is to a staff-plus interviewer.
- Asking the interviewer to enumerate the requirements for you.
- No close: running out of clock mid-sentence.
- Using CAP as "pick two of three."
- Answering "how would you scale" with a list of techniques and no binding constraint.
- Being unable to name anything you are unsure about.

---

## Cheat card

```
CLOCK      0-2   restate + declare the plan + ask agreement
           2-5   requirements: scale → 2-3 features → dominant NFR → non-goals
           5-8   estimation, out loud, ending in "so the design problem is ___"
           8-22  high-level BREADTH, ≤9 boxes, end to end, no depth
           22    CHECKPOINT: "two interesting problems; I'd start with X. Your call."
           22-40 DEEP DIVES. 2 done properly > 5 touched. THE SCORE LIVES HERE.
           40-45 close: built / key decision / unfinished / what's next

DEEP DIVE  name problem → constraint → 2-3 options → choose + why →
  SHAPE    cost accepted → one level below → VOLUNTEER the failure mode
           (that last step, unprompted, is the staff signal)

TRADEOFF   "A or B. I'd take A because <property of THIS problem>.
  TEMPLATE  What I'm giving up is C."   ← 8 seconds, use constantly
           Once per deep dive: "the argument for the other side is ___,
           and it wins if ___."

SCALE Q    1 ask what's scaling (users/data/req-per-user)
           2 name the component that breaks FIRST and why
           3 name the SYMPTOM (p99 up, errors flat, queue time up)
           4 fix, then what breaks next.  100x ≠ 10x with bigger numbers

RECOVER    stop · "let me back up, that doesn't work" · SAY WHY IN YOUR
           OWN WORDS · give the fix · name the new cost · move on
           new information → update.  pressure only → hold once, state
           what would change your mind.  second push → take it seriously.

SENIOR     "the cost I'm accepting is ___"
  PHRASES  "the failure mode of what I just described is ___"
           "what breaks first at 10x is ___ and the symptom is ___"
           "you know how X works, so let me go to the interesting part"
           "I don't know. Here's how I'd find out and what I'd assume"
           "I've changed my mind. Here's why."
           "I'd want to measure ___ before committing"

JUNIOR     tech names in the first 30s · "it depends" (full stop)
  TELLS    "we'd just add a cache" · "best practice" · "obviously"
           "what are the requirements?" · "microservices" as an answer
           "X is scalable" · CAP as pick-two-of-three · silence
           orphan nouns (any technology with no "because" attached)

NO         number the components · state direction explicitly ("fans out
WHITEBOARD in parallel to 2 and 3") · name them once, reuse the names
           practise one flagship system verbally, hands behind back

RULE       Every technology you name gets a "because <this problem>"
           in the SAME sentence. No orphan nouns.
```

## Sources

- [The 45-Minute System Design Interview Guide: A Step-by-Step Framework — DesignGurus](https://designgurus.substack.com/p/how-to-design-any-system-in-45-minutes) — accessed 2026-07-26
- [System Design Interviews: How to Fill 45 Minutes With Senior-Level Reasoning — DesignGurus](https://designgurus.substack.com/p/system-design-interview-a-7-step) — accessed 2026-07-26
- [A Framework For System Design Interviews — ByteByteGo](https://bytebytego.com/courses/system-design-interview/a-framework-for-system-design-interviews) — accessed 2026-07-26
- [Why Senior Engineers Fail System Design Interviews — Deep Engineering](https://deepengineering.substack.com/p/why-senior-engineers-fail-system-design-interviews) — accessed 2026-07-26
- [5 Keys to Staff-Level System Design Interviews — Hello Interview](https://www.hellointerview.com/blog/staff-level-system-design) — accessed 2026-07-26
- [What is the difference between a Senior and Staff engineer in a System Design Interview? — Taro](https://www.jointaro.com/question/5TaZMBhgxvdsKMoQ7qWi/what-is-the-difference-between-a-senior-and-staff-engineer-in-a-system-design-interview/) — accessed 2026-07-26
- [A Senior Engineer's Guide to the System Design Interview — interviewing.io](https://interviewing.io/guides/system-design-interview) — accessed 2026-07-26
- [Netflix System Design Interview (2026 Guide) — Exponent](https://www.tryexponent.com/blog/netflix-system-design-interview) — accessed 2026-07-26
- [Google Interview Process 2026: Loop & Committee — ResumeAdapter](https://www.resumeadapter.com/companies/google/interview-process) — accessed 2026-07-26
- [Meta Interview Process 2026: Rounds, AI-Assisted Coding & Behavioral Rubric Explained — ClavePrep](https://claveprep.com/blog/meta-interview-process-2026-guide) — accessed 2026-07-26

## Changelog
- 2026-07-26 — created
