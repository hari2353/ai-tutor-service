# MODULE SPEC — read this before writing any curriculum module

You are writing one module of a personal interview-prep curriculum for **Hari Siva Rami Dwarampudi**, a Principal AI Engineer with 7+ years at Cornerstone OnDemand who is **actively interviewing** for senior/staff/principal AI and backend roles at companies better than his current one.

He is a polyglot: Python primary, plus Java/Spring, Go, Node/React, PySpark, AWS. His resume includes production agentic AI (FastMCP, A2A, LangGraph), RAG at scale (Weaviate, ClickHouse HNSW, pgvector, BGE rerankers), an 8-service recommendation platform, LLM serving on SageMaker with vLLM, a Java→Python migration, a ClickHouse OOM fix, OWASP remediation, 22-locale inference hardening, PySpark/EMR contextual bandits, MongoDB race conditions, and an 89% ETL latency reduction.

Write for someone at that level. Do not explain what an API is.

---

## Sources — non-negotiable

1. **`WebSearch` before writing anything version-dependent.** Frameworks, APIs, model capabilities, cloud services, library defaults. Do not write these from memory. Use today's real date — do not assume the dates in the examples below are current.
2. **Mine real interview questions.** Search for what is *actually asked* on this topic — Glassdoor/Blind/levels.fyi write-ups, Medium interview retrospectives, and the structure used by `github.com/pubalisen/ai-ml-interview-deep-dives` (question → what's tested → mechanical answer → trap). Prefer real reported questions over invented ones.
3. **Cite anything current** as `[title](url) — accessed 2026-07-26`.
4. **Prefer primary sources** — the original paper, the official docs, the actual release notes — over blog summaries.

---

## File layout

All paths below are relative to the repo root (the directory containing `CONTENT-STATUS.md`).

Write to `curriculum/<track-dir>/<NN>-<slug>.md` where `NN` is the module's order+1 zero-padded to 2 digits.

**Do NOT touch `app/data/flashcards.json` or `app/data/drills.json`** — they are generated aggregates, other agents write concurrently, and a hand-edit is overwritten on the next build. Instead write:

- `app/data/cards/<module-id>.json` → `{"flashcards":[{"id":"<module-id>-c1","topic":"<Title>","q":"...","a":"...","module":"<module-id>"}]}`
- `app/data/drillsets/<module-id>.json` → `{"drills":[{"id":"<module-id>-d1","module":"<module-id>","q":"...","a":"...","difficulty":"warmup|mid|staff"}]}`

`build_data.py` merges these by id, so re-running after an edit corrects the aggregate rather than duplicating the row.

**If you are one of several agents writing in parallel, do NOT run `python app/build_data.py`** — the orchestrator runs it once at the end. If you are writing a single module on your own (the `/tutor-deepdive` path), run it yourself when you finish. Either way the module is invisible to the app until it runs.

---

## House format — every section required, in this order

```markdown
# <Title>

> **Track:** <id + name> · **Time:** <N>h · **Prereqs:** <...> · **Updated:** 2026-07-26
> **Module id:** `<module-id>` · **Tags:** <tags>
> **Lab:** `labs/<lang>/<NN>-<slug>/`   (only if one should exist)

## The 30-second version
3-5 sentences. What he says when an interviewer asks this cold. No hedging, no
"it depends" without saying what it depends on. WRITE THIS LAST.

## Why this gets asked
What the interviewer is actually probing, and which production failure they have
personally lived through that makes them ask it.

---

## Lineage: past → present → future
THREE paragraphs, all required:
- **What came before** — the approach this replaced, and the specific pain that
  killed it. Name papers/systems and years.
- **Where it stands now** — current consensus, the LIVE disagreements, and what is
  actually deployed at scale versus merely published.
- **Where it's heading** — direction of travel, with confidence levels stated.
  Explicitly flag what is speculative.

---

## Mental model
The one diagram or analogy that makes it click. ASCII diagrams preferred.

## How it actually works
The mechanical explanation, one level below where most people stop. Real code,
real numbers, real config. Derive rather than assert.

## Build it from scratch
Minimal from-zero runnable implementation. Reference the matching lab folder.

## How it's done in production
The framework/managed version and what it adds. Include a failure-mode table:
| Symptom | Cause | Fix |

## Tradeoffs & when NOT to use it
The senior signal lives here. Every technology has a wrong context. Be specific.

---

## Interview questions

### Q1 — <the question as actually asked>
**Testing:** <what they want to see>
**Answer:** <mechanical, specific, with numbers>
**Follow-up trap:** <the second question that catches people, and how to survive it>

<10-20 of these, escalating warmup → mid → staff/principal.>

## Red flags that fail you
- <things candidates say that end the interview>

## Cheat card
```
8-15 lines. Bare facts, numbers, thresholds, syntax. One screen. This becomes
the flashcards, so make every line atomic.
```

## Sources
- [title](url) — accessed 2026-07-26

## Changelog
- 2026-07-26 — created
```

---

## Quality checklist — your module will be reviewed against exactly this

1. 30-second version exists and is genuinely 3-5 sentences.
2. Lineage has all three parts, with the *pain* that killed the old approach named.
3. **At least 5 concrete numbers** (latencies, defaults, thresholds, complexities, costs).
4. At least one **named failure mode with its observable symptom** (what you'd see in a log or trace).
5. **10+ interview questions, every one with a follow-up trap.**
6. A real "when NOT to use it" — not a token paragraph.
7. Sources cited with access dates for anything version-dependent.
8. Code either runs or is marked `# untested sketch`.
9. No marketing voice. If a tool is usually the wrong choice, say so plainly.
10. Cheat card is one screen and atomic.

Failing 1-7 sends the module back.

---

## Voice

- **Numbers over adjectives.** "~50ms p99 at 1k QPS on c6i.2xlarge" beats "fast".
- **Show the failure.** Name what breaks and the symptom.
- **State the counter-argument.** Where practitioners genuinely disagree, say so rather than picking a side silently.
- Direct. No filler, no "in today's fast-paced world", no restating the question.
- Never use em-dashes as a stylistic tic; normal prose punctuation.

---

## Exemplars — read at least one before writing

- `curriculum/21-architecture-principles/06-resilience-catalogue.md`
- `curriculum/07-agentic-ai/01-agent-loop-from-scratch.md`

These are the bar. If your module is thinner than these, it is not finished.

## When you finish

Report only: the file paths written, module count, flashcard count, drill count, and
any claim you could not verify with a source. Do not summarize the content.
