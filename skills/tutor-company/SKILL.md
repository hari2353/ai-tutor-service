---
name: tutor-company
description: Turn a job description into a researched interview prep pack — the company's actual stack, their loop structure and bar, an honest fit table against the user's resume, 25 likely questions with answers, and their real gaps — then role-play as that company's interviewer. Use when the user says /tutor-company, pastes a JD, or says "I have an interview at X", "prep me for X", "what will X ask me".
---

# tutor-company

Prep against a **specific** loop, not a generic one. The output is a pack on disk plus, on request, a role-played round.

**Repo root** (`$ROOT`): `C:\Users\medic\OneDrive\Documents\ai-tutor-service`

## 1. Inputs

The JD text (pasted or a URL), the company name, and the role. Ask for the **stage** (recruiter screen / tech screen / onsite) and the **date** — both change what gets prioritised. If the JD is a URL, `WebFetch` it.

## 2. Research

`WebSearch` for, and label each finding as **verified** (primary source) or **inferred**:

- **Stack** — engineering blog, GitHub org, job postings across the company, conference talks. What they actually run, not what the JD lists as nice-to-have.
- **Loop structure** — Glassdoor/Blind/levels.fyi write-ups and interview retrospectives. Number of rounds, which are coding vs design vs behavioral, whether there is a take-home, who the bar-raiser equivalent is.
- **The bar** — level mapping, and what "principal" means there specifically. It differs enormously between an AI startup and a FAANG.
- **Recent context** — funding, launches, layoffs, a public incident, a migration they blogged about. This is where good questions to ask them come from.

Say plainly when something could not be found. An invented loop structure is worse than "unknown — ask the recruiter".

## 3. The fit table — honest, both directions

Read the user's resume material in `$ROOT/curriculum/10-system-design/` (resume systems) and `$ROOT/curriculum/14-behavioral-principal/` (STAR bank) if written; otherwise ask for the resume.

| JD requirement | Their evidence | Strength | The story to tell |
|---|---|---|---|
| Production LLM serving | vLLM on SageMaker, 22-locale hardening | **strong** | the inference-hardening story with the latency numbers |
| Kubernetes at scale | some, not deep | **thin** | do not volunteer; if pushed, the honest version |
| Go services | Java→Python migration, not Go in prod | **gap** | say so, then pivot to language-selection judgment |

Mark gaps as gaps. The point of this table is to know before the interview does.

## 4. The pack

Write to `$ROOT/mocks/company/<company>.md`:

```markdown
# <Company> — <Role> · prep pack
> generated <date> · stage: <x> · interview: <date>

## The 30-second read
<Who they are, what they actually build, why this role exists. 4 sentences.>

## Their stack
| Layer | What they use | Confidence | Your exposure |

## The loop
<Rounds, order, length, what each screens for. Sources cited.>

## Fit
<the table>

## 25 likely questions
<Grouped: their stack (10) · the role's core (8) · behavioral/values (4) · your resume (3).
Each with: what they're testing · the answer to give · the follow-up trap.>

## Your gaps, ranked
<What they will ask that the user cannot currently answer, ordered by likelihood ×
cost of missing it. Each with the module that fixes it and the hours needed.>

## Questions to ask them
<6. Specific to their recent context. Nothing googleable.>

## Do not say
<Phrases that read badly at this company specifically.>
```

## 5. The study plan

Given the days until the interview, produce a schedule that fits. Sprint order is suspended — this is the override. Weekend 8 (resume defense, STAR bank) is the highest-ROI block for any loop and comes first unless a gap is more urgent.

If there is not enough time to close a gap, say so and give the **honest deflection** instead: how to acknowledge a gap without losing the room. Faking depth is what actually ends interviews.

## 6. Role-play

When asked, switch to being their interviewer. Follow `/tutor-mock` for behaviour and scoring, with these changes:

- Use **their** loop structure and their bar, not the generic one.
- Use their vocabulary and their systems in the questions.
- Match their culture: Amazon → LPs and the bar-raiser's "tell me about a time you were wrong"; an AI startup → depth plus "would you actually ship this"; big-tech infra → scale numbers and failure modes.
- Announce which round of their loop you are running, then stay in character.

## Rules

- Label verified vs inferred. Never present a guessed loop structure as fact.
- The fit table must contain at least one honest gap. If it does not, look harder.
- Do not editorialise about the company. The user is choosing whether to work there; give them the facts.
