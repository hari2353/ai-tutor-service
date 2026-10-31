# Build Projects That Interviewers Believe: 15 AI Builds + 10 Coding Warmups

> **Track:** T15 Interview Simulator · **Time:** 2h · **Prereqs:** T15-resume-ats-evidence, T14-star-bank
> **Module id:** `T15-build-projects` · **Tags:** interview, practice, portfolio

## The 30-second version

Interview claims are evidence-shaped, and the cheapest reliable evidence is a *finished, deployed, eval'd* project — not a course certificate. This module is the concrete menu: **15 AI-engineering builds** ordered beginner → advanced (each with the concepts it proves and the outcome you show), **10 coding warm-up problems** for the AI-engineer loop (each covering one interview surface: data structures, async, data, SQL, ML-from-scratch, and API integration), and the **repos that back both**. The rule that makes them interview currency rather than hobby work: every build ends with a *measurable proof* — cost per 1,000 requests measured, a CI test proving user-data isolation, a before/after table on your RAG upgrades, an MCP server someone else installed, a vulnerability you found and fixed — because "I did a course" transcribes to nothing in interview notes, while "here's the dashboard and the failure I caught" transcribes directly into a STAR story.

## Why this gets asked

AI-engineering hiring loops have a structural gap: most candidates can talk about RAG, agents and fine-tuning at the same vocabulary level, because the vocabulary is free. What discriminates is the sixty-second window where you show the eval set, the trace, the cost curve or the red-team suite and the interviewer's follow-up chain either continues or dies. These projects are chosen so that each one manufactures that window — and so that the *sum* covers the loop: a chatbot or extractor proves API and structured-output basics, a read-only SQL assistant proves guardrail thinking, a production RAG service proves deployment and observability, a red-team suite proves safety maturity. Hiring managers reading a portfolio scan for exactly that distribution, which is why "3-5 builds + one deployed app" beats fifteen half-finished repos.

---

## Lineage: past → present → future

**What came before.** The 2010s portfolio cannon — to-do apps, clones, Kaggle notebooks — stopped working when AI engineering arrived, because model calls erased most of the code: a chatbot is ~40 lines once you have an SDK, so a to-do level project no longer demonstrates anything the resume doesn't say. What replaced it: builds whose *difficulty lives in the surrounding engineering* (validation, retrieval quality, evals, deployment, failure handling), not in calling the model. Roadmap-style curricula (e.g. the widely-shared 2026 AI-engineering roadmaps) have converged on this shape: sections ending in checkpoints, one project per phase, evals run like unit tests in CI.

**Where it stands now.** Public discoverable proof is the norm, sites from resume-screening to offer-decision increasingly ask for repo links, and the strongest signal chain — issues closed by you, README with a live demo, an eval file in CI — is fully within reach. The 15-project menu below is aligned with that reality: each project lists the interview concepts it exercises, the difficulty, and the finished-shape outcome, so you can pick by gap ("I have no observability story") rather than by novelty.

**Where it's heading.** The differentiating builds this year are the ones that *operate* rather than merely serve: a capstone with real users, dashboards and an incident you debugged from traces. Expect interviewers to keep moving one question earlier in the chain — from "what did you build" to "what did it cost, what broke, what did the eval catch" — which means the artefacts you leave in the project (eval script, cost table, postmortem) matter more than the feature list. High confidence: AI-assisted coding makes the *building* cheaper, so the *evidence trail* is what stays scarce.

---

## Mental model

A portfolio is a spread of bets across the interview loop, not a list of apps.

```
  LOOP SURFACE            PROVED BY BUILD                      TYPICAL FOLLOW-UP YOU SURVIVE
  ─────────────────       ──────────────────────               ─────────────────────────────
  API + structured out    invoice extractor                    "what if the model returns bad JSON?"
  Retrieval quality       PDF QA with citations                "how do you know recall@k improved?"
  Tool safety             read-only SQL assistant              "how do you stop DROP TABLE?"
  Agent autonomy          research agent w/ step budget        "how do you bound runaway loops?"
  Serving + cost          FastAPI + streaming + cache          "what does one request cost you?"
  Safety                  red-team suite + PII masking         "what injection did you catch?"
  Evals                   prompt eval harness in CI            "who calibrates your judge?"
```

Pick rows you're weakest in, not rows you'd enjoy repeating.

---

## Recognition heuristics — choose by the gap it fills

- "I have no AI project" → CLI chatbot, summarizer, invoice extractor (beginner tier; finish all three inside two weekends).
- "I can't prove RAG quality" → PDF question-answering with citations; the eval file is the deliverable.
- "I've never guarded a tool" → read-only SQL assistant or support assistant with tools (least-privilege is the interview line).
- "I've never measured anything" → prompt eval harness (golden set, judge, report) plus measured cost on it.
- "I've never shipped" → production RAG service: FastAPI + Docker + tracing + dashboards; keep it deployed.
- "I've never broken anything" → red-team suite (prompt injection, data-isolation vulnerabilities you found and fixed).
- "I've never played with the protocol layer" → MCP tool server that someone else installs (third-party installability is the proof).

---

## The 15 AI builds (with the proof each one leaves behind)

**Beginner (finish inside the first two weeks of the module)**

1. **CLI chatbot** — API calls, system prompts, history → *proof:* custom-persona bot with conversation memory.
2. **Text summarizer** — prompt length control → *proof:* tool that handles 50k-character input without truncation failures.
3. **Invoice extractor** — structured output, pydantic → *proof:* scans a real PDF invoice set and prints validated JSON with error counts.
4. **Prompt comparison tool** — A/B prompts over a fixed case set → *proof:* a table of pass rates, not vibes.
5. **Semantic notes search** — embeddings + cosine similarity → *proof:* search over your own notes that meaning-matches (code-connected follow-up: why bigger chunks changed nothing).

**Intermediate**

6. **PDF question answering** — RAG, chunking, citations → *proof:* chat over your documents, every answer carrying the source page.
7. **Support assistant with tools** — function calling + validation → *proof:* bot that looks up real orders, with tools validated before execution.
8. **Read-only SQL assistant** — schema prompts, safe execution → *proof:* natural-language queries against a real DB that *provably* cannot mutate it.
9. **Prompt eval harness** — test sets, judges, metrics → *proof:* CI-style eval report that fails the build on regression.
10. **Resume screener** — structured output, guardrails, bias checks → *proof:* scored, explainable shortlist with a bias note on the rubric.

**Advanced**

11. **Research agent** — tool loop, step budget, memory → *proof:* agent producing cited reports that terminates within budget.
12. **Production RAG service** — FastAPI, Docker, caching, tracing → *proof:* deployed API with dashboards and a latency/cost bill.
13. **LoRA vs prompting study** — fine-tuning, evaluation → *proof:* an honest benchmark-plus-cost comparison, including the case where fine-tuning lost.
14. **Red-team suite** — prompt injection, safety tests → *proof:* attack script + the fixes; log the vulnerability you found in your own system.
15. **Capstone product** — end-to-end, evals, monitoring, real users → *proof:* the portfolio app with a live demo and user feedback.

---

## The 10 coding warm-ups (one per interview surface)

Each of these came from a widely-shared AI-engineer loop prep sheet, and each one is a surface the model-call era no longer trains:

| # | Problem | Surface it defends |
|---|---|---|
| 1 | LRU cache, efficient get/put from scratch | data structures under a contract (→ `T02-design-problems-caches`) |
| 2 | Process a large log file, return most frequent error types | streaming-minded file work, hashing |
| 3 | Async function calling multiple APIs, with retries + timeouts | concurrency under failure |
| 4 | Clean a pandas dataset (missing, dupes, mixed formats) | data hygiene |
| 5 | SQL: top-3 products by revenue per category | window functions in one query |
| 6 | Linear regression with NumPy only | math you never get to skip |
| 7 | Classification pipeline: preprocessing + CV + eval | sklearn-shaped rigor |
| 8 | Precision/recall/F1 from raw predictions, no sklearn metrics | metric literacy |
| 9 | Semantic search end-to-end (embed + cosine) | the engineer's version of "I know RAG" |
| 10 | FastAPI endpoint calling an LLM: structured output + error handling | the production loop in one file |

If the minutes are too short for a build block, the gamified-learning canon fills idle ones without an editor: **TensorFlow Playground** (build a neural net visually in-browser), **Transformer Explainer** (poloclub's next-token visualization), **Teachable Machine** (train a small image/audio model in minutes), **SQL Murder Mystery** (a full detective story solved with SQL joins), **CodeDash**-style Python adventure games, and **TrickGuard** (an AI-safety game — prompt your way past a model's guardrails). None of these replaces a build; they exist for pattern-intuition days and for the "I've never touched SQL" interview slice — 15 minutes of Murder Mystery beats an hour of passive tutorial for finding out how much SQL you actually know.

And the answer to all of them is never just the code — rehearse the follow-up chain from the source sheet: time and space complexity, edge cases, error handling, testing, trade-offs. That list is what the "explain" half of the question is buying.

## Failure-mode project warm-ups (5 more, from aishwarya_srinivasan's 2026 list)

These five are short builds whose whole point is the **failure case the interviewer will probe** — each one is a one-evening exercise that proves you've thought about what breaks:

| # | Project | What it proves | TEST THIS |
|---|---|---|---|
| 1 | Company Q&A assistant (permission-filtered retrieval) | Retrieval + access control | An employee asks for a restricted salary file — does it refuse? |
| 2 | Support request tracker (intake-to-resolution) | State + human handoffs | The system crashes after approval — can it resume safely? |
| 3 | Invoice checker (AI extraction + deterministic checks) | AI extraction + code validation | The extracted total disagrees with the line items |
| 4 | Customer data cleaner (onboarding) | Data mapping + exception handling | A file has duplicate IDs and missing required fields |
| 5 | Operations dashboard (command center) | Tool use + reliable action loops | An action times out — check status before retrying |

Pair each with the portfolio checklist that goes with them: customer problem, architecture + tradeoffs, permissions + failure cases, eval results, demo + clear README. A working demo is the beginning; the decisions visible in the README are what read as engineering.

---

## How it actually works — the interview conversion step

Building is the expensive half; converting it into interview currency is the part people skip:

- **Name the artifact in the STAR bank.** Each finished project gets one STAR story whose *Result* is a number (cost, latency, pass-rate, bugs caught) — wired into `T14-star-bank` and the resume module's evidence rules.
- **Leave the eval file in the repo.** A `evals/` directory with cases and a CI badge is the single strongest "this person operates models" signal available from a repo link.
- **Deploy one, and only one, fully.** A capstone with a live URL beats five dead repos; the deployed app is the only artefact an interviewer can poke themselves.
- **Write the README for the interviewer.** Show the failure you caught, not the feature list: "found my prompt was being injected by fetched page X; scoped permissions after" reads like engineering; "GPT-4-powered" reads like marketing.

## Common traps

- Fifteen projects at 20% beats zero — the menu is for *choosing by gap*, not for completionism.
- Model-only projects ("wrapper app") that carry no surrounding engineering; the interviewer's follow-up chain dies at question one.
- Portfolio metrics invented post-hoc: measure during the build (cost per request, pass-rate, coverage), not for the resume.
- Kaggle-style notebooks presented as apps: fine for ML-engineer loops, weak for AI-engineer loops where serving and failure behavior are the differentiators.

## Interview questions

1. **"Walk me through one project end-to-end — the failure, not the feature."** Pick the project with your best measurable proof and lead with it.
2. **"How did you know the RAG upgrade worked?"** The proof-of-work answer: a before/after table on retrieval recall and answer faithfulness, from the eval harness module (`T08-eval-harness` `T06-rag-eval`).
3. **"What does one request cost you, and why?"** Measured cost per 1k requests once on each surface (chat, retrieval-round-trip, judge pass) — proof beats estimate.
4. **"Show me where your agent could run away."** Step budget + stop rule + human-approval point from builds 11/14, and the reason you reused a third-party harness for it.
5. **"What's the security story for your tools?"** Least privilege + validation + the vulnerability you found and fixed, alive in items 8/10/14.

## Red flags that fail you

- "I took a 100-day course" answered instead of "I built X and measured Y."
- Projects with no eval, no cost, no failure — vocabulary without proof.
- Public repos with no README or a dead demo link — worst possible print for a systems person.

## Cheat card

- Pick builds **by loop-surface gap**, not novelty; finish beginner tier first, deploy exactly one capstone.
- Every build ends in a **number**: cost, recall@k, pass-rate, latency, bugs caught.
- The 10 warm-ups cover data structures, streaming, async-retries, pandas, SQL windows, NumPy math, sklearn-pipeline, metric math, embeddings, FastAPI+LLM — one per loop surface.
- Back it with repos: OpenAI Cookbook (worked examples), Coding Interview University (basics core), System Design Primer (design baseline), AlgoVault (pattern bank).
- Answer shape: "I built X, it cost Y, the eval caught Z, here's the dashboard."

## Sources

- [decode_leox — AI Engineering Roadmap 2026 (slides)](https://www.instagram.com/p/Deop_YijUR2/) — 19-section curriculum, 15-project menu, 360h path (accessed 2026-10-31)
- [madhurmehta — AI engineer coding interview 10 problems](https://www.instagram.com/reel/Deo8kNtA1RK/) — problem list + interview meta (accessed 2026-10-31)
- [datasciencebrain — Zero-to-Hero 100-day GenAI plan — proof-of-work framing](https://www.instagram.com/p/DeUEdtxmOXL/) (accessed 2026-10-31)
- [codewithupasana — 5 GitHub repos for the resource library](https://www.instagram.com/p/Dd8EJmMGjDp/) (accessed 2026-10-31)
- [DdxhFHTR8cm — 6 gamified AI-learning sites: TensorFlow Playground, Transformer Explainer, Teachable Machine, SQL Murder Mystery, CodeDash, TrickGuard](https://www.instagram.com/reel/DdxhFHTR8cm/) (accessed 2026-10-31)
- [aishwarya_srinivasan — "5 AI Projects to Build Before 2026 Ends" (Company Q&A w/ permission filter, support tracker w/ crash-resume, invoice checker w/ deterministic validation, customer data cleaner, ops dashboard w/ timeout-safe retries) + portfolio checklist](https://www.instagram.com/p/DeKWBPuE9Kj/) (accessed 2026-10-31)

## Changelog

- 2026-10-31: Created — the interview-prep project menu and coding warm-ups were the batch's only genuine interview-side gap; rounds and resume modules already existed.
- 2026-10-31: Added the gamified idle-minutes canon (playgrounds, Murder Mystery, TrickGuard) after the warm-ups table.
