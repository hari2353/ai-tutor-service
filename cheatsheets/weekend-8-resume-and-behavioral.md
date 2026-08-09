# Weekend 8 — Your Systems, Your Stories, and How Each Company Scores Them

This weekend decides interviews because it's the only round type where the interviewer knows you cannot bluff — every question is answerable from ground truth you either have indexed or don't, and the failure mode isn't lack of knowledge, it's lack of retrieval speed under pressure.

## Your Flagship Systems as Formal Design Docs

**30-sec:** "Walk me through something you built" is the round most likely to be failed, because every follow-up is checkable. Five systems are strong enough to present cold: the Skills Intelligence Platform (54,486 skills, 22 locales, ClickHouse HNSW + BGE reranking), the 8-service recommendation platform (2M+ users, ~25% engagement uplift), the A2A + FastMCP multi-agent content pipeline, the LLM serving platform (self-hosted vLLM on SageMaker + Bedrock batch), and Query Crafter (NL-to-SQL over Trino). Write each up as: context, requirements (+non-goals), a ≤9-box architecture diagram reproducible in 90 seconds, decisions with the rejected alternative and accepted cost, data model, scale numbers, failure modes stated symptom-first, and what you'd change now.

**Doc shape:** context → requirements+non-goals → architecture → decisions (chose X over Y because Z, accepted cost C) → data model → scale numbers → failure modes (symptom first) → what I'd change.

**Per-system facts:**

| System | Core numbers | The load-bearing decision | Known gap |
|---|---|---|---|
| S1 Skills | 54,486 skills, 22 locales, 1.2M+ rows, Titan v2 512-dim, ClickHouse HNSW + BGE-Reranker-Large | vectors ≈2.5 GB float32 | OOM = exit 137, no traceback → fixed by pagination + `gc.collect` at page bounds |
| S2 Recs | 8 services, 307 commits, 178K+ LOC, 2M+ users, ~25% uplift | boundaries drawn on independent scaling+failure, not entities; bandit not supervised (logged policy starves new content) | no off-policy eval (IPS) |
| S3 Agents | 3 agents over A2A, shared capabilities as FastMCP servers | MCP = tool contract, A2A = inter-agent messaging | step cap + token budget live outside agent logic |
| S4 Serving | vLLM continuous batching + PagedAttention | concurrency limited by KV cache, not FLOPs | rate limiting must bound concurrency, not retry |
| S5 Query Crafter | RAG over schema+glossary+prior queries → guardrail → Trino | always shows the generated SQL; read-only + scan/row/time limits | correctness never measured, only adoption |

**Kill switches (what fails this round):** no alternative rejected, an invented number, a 25-box diagram, "we" with no personal decision, no stated non-goals, failure modes described outcome-first instead of symptom-first.

## 30-Story STAR Bank Mined From Your Resume

**30-sec:** A behavioural loop asks 12–18 questions across a career's worth of bullets; every one should be answerable from a pre-indexed set. Convert each bullet into Situation/Task/Action/Result plus the two things most candidates omit: the alternative you rejected and why, and what you'd do differently now. Tag each story to competencies and to specific company rubric language so you retrieve by tag under pressure, not by memory. The bar is "can you articulate the decision and own the tradeoff, with a number" — the failure mode is four minutes of situation with no stated decision.

**Answer shape (60-sec version = ~9 sentences):** Situation 10% · Task 10% · Action 50% · Result 15% · why-not-X 10% · what I'd redo 5%. First person singular in every action sentence — "I decided," not "we decided."

**Must-have stories you cannot enter a loop without:** disagreed and was wrong · a real failure with a real cost · said no and lost · influenced without authority · reframed a wrong requirement · prevented an expensive mistake.

**Kill switches:** "we" with no personal decision, no number in the result, no rejected alternative stated, a four-minute situation, a costless failure, telling the same story twice in one loop, bad-mouthing a former employer.

## The 45-Minute System Design Communication Framework

**30-sec:** The round is a time-allocation problem before a technical one: ~5 min requirements, 3 estimation, 12–15 high-level design, 15–20 deep dives, 3–5 close — and deep-dive weight dominates scoring while most candidates spend 60% of their time on the diagram instead. Senior engineers fail on communication, not knowledge: naming technologies without grounding them in the specific problem reads as performing knowledge; describing components without discussing tradeoffs is the single most common gap. At staff+ you drive: you set the agenda out loud, announce what you're skipping, and offer the interviewer a choice of depth.

**Clock:** 0–2 restate+plan · 2–5 requirements · 5–8 estimation → "so the design problem is ___" · 8–22 high-level breadth (≤9 boxes, no depth) · 22 checkpoint: "two interesting problems, I'd start with X, your call" · 22–40 deep dives (2 done properly beats 5 touched — the score lives here) · 40–45 close.

**Deep-dive shape:** name problem → constraint → 2–3 options → choose + why → cost accepted → one level below → volunteer the failure mode unprompted (the staff-level signal).

**Recovery:** stop → "let me back up, that doesn't work" → say why in your own words → give the fix → name the new cost → move on. New information → update. Pressure alone → hold once, state what would change your mind.

**Junior tells to avoid:** tech names in the first 30 seconds, "it depends" full stop, "we'd just add a cache," "best practice," "obviously," CAP as pick-two-of-three, orphan nouns (any technology with no "because" attached).

## Amazon LPs, Google, Meta, Microsoft, Netflix, AI Startups

**30-sec:** The same 30 stories pass or fail depending on whose rubric is scoring them — each company optimises for something structurally different, and telling the same story in the same shape everywhere is the mistake. The fix is choosing which framing of each story fits the rubric in front of you.

| Company | Scored on | Structural quirk |
|---|---|---|
| Amazon | 16 named LPs, 2–3 per interviewer; heaviest: Dive Deep, Deliver Results, Invent & Simplify, Bias for Action | Bar Raiser is from outside the team and has veto power; 4–5 rounds (7–8 at Principal) |
| Google | RRK, GCA, Leadership, Googleyness (intellectual humility) | Hiring committee never met you — scores written evidence only; if it doesn't transcribe, it doesn't count |
| Meta | Ownership, conflict, ambiguity, mistakes ("Jedi" round, 45 min) | E6+ onsite adds an AI-assisted coding round; bar = disagreement across 2+ teams, org-level impact |
| Microsoft | Competencies per round + growth mindset ("learn-it-all") | Ends with an "As Appropriate" round targeted at your weakest earlier answer |
| Netflix | Keeper test + written culture memo; candour, context-over-control | Conversational, often no whiteboard, ~7 interviews |
| AI labs (OpenAI/Anthropic) | Paid work trial performance, not interview performance | OpenAI: GATE screen → 48h paid trial → 4–6 loop. Anthropic: 5 stages/4–6wk, take-home, 4-level coding |

## If you remember nothing else

1. Present flagship systems as: context → requirements+non-goals → architecture → decisions (rejected alternative + accepted cost) → scale → failure modes stated symptom-first.
2. Every STAR answer needs the rejected alternative and what you'd redo now — these are the two things most candidates omit and every senior interviewer scores.
3. First-person-singular action sentences only. "I decided," never "we decided." A number in the result is non-negotiable.
4. In a 45-minute design round, 2 deep dives done properly beat 5 touched — that's where the score actually lives, not the high-level diagram.
5. Volunteer the failure mode of your own design unprompted — that single move is the strongest staff-level signal available.
6. Recovering from a wrong turn (stop, say why, fix, name new cost, move on) scores higher than never being wrong.
7. Amazon's Bar Raiser is from outside the team and can veto regardless of the rest of the panel's opinion.
8. Google's hiring committee never meets you — if your story doesn't transcribe into written evidence, it doesn't count, no matter how well you told it live.

## Numbers table

| Fact | Value |
|---|---|
| Flagship diagram size / time | ≤9 boxes / 90 seconds |
| STAR answer time / sentence budget | ~60 sec / ~9 sentences |
| STAR shape split | S10% T10% A50% R15% why-not-X10% redo5% |
| Behavioural loop question count | 12–18 questions |
| Design round clock | 0–2 / 2–5 / 5–8 / 8–22 / 22–40 / 40–45 min |
| Design round diagram box cap | ≤9 |
| Amazon LP count / rounds | 16 LPs / 4–5 rounds (7–8 at Principal) |
| Amazon LPs per interviewer | 2–3 |
| Meta behavioural round length | 45 min |
| Netflix interview count | ~7 |
| Anthropic process length | 5 stages, 4–6 weeks |
| OpenAI work trial length | 48 hours, paid |
