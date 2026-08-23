# AI Tutor Service

[![ci](https://github.com/hari2353/ai-tutor-service/actions/workflows/ci.yml/badge.svg)](https://github.com/hari2353/ai-tutor-service/actions/workflows/ci.yml)

Personal interview-and-mastery system for **Hari Siva Rami Dwarampudi** — Principal AI Engineer, actively interviewing.

**36 tracks · 454 modules · ~1,048 hours** — with a **32-module, ~89-hour, 10-weekend sprint** on top that's what actually decides your next loop. Fully local, free tier, zero cloud spend.

> Numbers drift as content lands. The live counts are always in `CONTENT-STATUS.md`
> (regenerate with `python app/build_data.py`). Historical planning docs live in `docs/history/`.

---

## Open it

Double-click:

```
app\index.html
```

No server, no build step, no install. State saves to your browser; export it from the **Save/Load** tab into `progress/progress.json` to version it or move machines.

---

## Daily use — just talk to Claude

| Say this | What happens |
|---|---|
| `/tutor-start` | Today's quest, due flashcards, where you left off |
| `/tutor-deepdive <topic>` | Writes a new interview-grade module in the house format |
| `/tutor-lab <topic>` | Generates a from-scratch, test-driven lab |
| `/tutor-drill <topic>` | Fast Socratic quiz, graded, weak spots logged |
| `/tutor-mock <round>` | Scored mock interview against a real rubric |
| `/tutor-review <path>` | Principal-level code review, as an interviewer would |
| `/tutor-cheatsheet <topic>` | One-page revision sheet + flashcards |
| `/tutor-progress` | Where you actually stand, and the one thing to do next |
| **`/tutor-update`** | **Pulls the delta from AWS/Azure/GCP release feeds + the AI stack since the last run** |
| `/tutor-add` | Appends new content and reindexes the app |
| **`/tutor-company`** | **Paste a job description → researched prep pack + role-play as that company's interviewer** |
| **`/tutor-debrief`** | **Report back after a real interview → it logs the questions, diagnoses the failure type, and re-prioritises the curriculum automatically** |

All twelve skills locate the repo by walking up to the directory containing
`CONTENT-STATUS.md` — they work from any subdirectory on any machine, no hardcoded
paths. After editing one:

```powershell
powershell -ExecutionPolicy Bypass -File skills\install.ps1
```

The last two close the loop: prep against a real JD → interview → debrief → the plan updates itself from real evidence. Any topic asked in two or more interviews gets auto-promoted into the sprint.

---

## Layout

```
README.md        start here — what this is, how to drive it
ROADMAP.md       weekend-by-weekend schedule
CONTENT-STATUS.md  auto-generated burn-down (the honest number)
LEARNING-PATH.md   prerequisite-ordered reading path (auto-generated)
skills/          the 12 /tutor-* skills (source of truth) + install.ps1
app/             the gamified tutor (index.html + engine + generated data)
  build_data.py  TRACKS spec -> .json/.js + CONTENT-STATUS.md
  tests/run.ps1  full suite on Windows (run.sh for bash)
curriculum/      theory — deep dives, one .md per concept, 36 tracks incl. clouds
clouds/          AWS · Azure · GCP service atlases + changelogs
  CROSS-CLOUD-MAP.md    the equivalence table to recite in interviews
labs/            practice — py · java · go · rust · ts · infra, all test-driven
cheatsheets/     32 auto-generated sprint one-pagers (+ README index)
drills/          question banks
mocks/           your scored transcripts
progress/        exported state · CONFIRM-CHECKLIST.md (facts only you can fill)
scripts/         security gate · cheatsheet generator · auditable repo fixes
SECURITY.md      privacy classes + pre-upload checklist
docs/history/    PLAN / PIPELINE / HANDOFF as they were at each milestone
templates/       MODULE-SPEC.md — the contract every module is written against
```

---

## Three tiers

**SPRINT** — 32 modules, ~89h, 10 weekends. Weekend-ordered and the quest generator follows that order exactly. Agent loops, LangGraph durability, RAG retrieval, context engineering, attention + inference serving, design craft (estimation/diagramming/method), eval, MVCC, your resume systems, harness engineering, and a zero-to-production capstone. This is the plan.

**Phase A — core.** Everything else you'd be embarrassed not to know for these roles: DSA + graph algorithms, networking & protocols (TCP, gRPC, HTTP semantics, curl), auth & appsec (JWT, OAuth2/OIDC), data engineering + EMR, frontend & UI engineering, testing, Docker/Kubernetes/Git/debugging, AI-assisted architecture, applied NLP/marketing ML, the AWS atlas.

**Phase B — mastery.** Computer systems from transistor to runtime, reinforcement learning from MDPs to PPO, Rust, classical ML and deep learning from scratch, quant finance and Basel, blockchain, quantum, frontier AI (world models, JEPA, Cosmos, robotics).

The app handles the sequencing. Sprint modules bypass prerequisite gating — if it's in the sprint you need it now.

**~1,043 hours is well over two years of weekends, and that's intentional.** It's a reference library with a sprint on top, not a queue to drain. Do the sprint; pull on the rest when a topic comes up.

---

## Gamification

XP per activity → 10 levels (Initiate → **Principal Architect**) · weekend streaks · 42 badges · SM-2 spaced repetition · ~4,800 flashcards · ~4,000 drills in the Drills tab · prereq-gated skill tree · boss battles every ~12 modules.

The spaced repetition matters more than it sounds for a weekend-only cadence: you forget between sessions, and the scheduler is what stops that.

---

## Test everything

One command on Windows:

```powershell
powershell -ExecutionPolicy Bypass -File app\tests\run.ps1
```

(bash equivalent: `bash app/tests/run.sh`) — rebuilds data, runs the DOM/state tests, the SM-2 scheduler tests, the mechanical review gate over all written modules, and every lab that has a `tests/` directory. A missing pytest shows as SKIPPED, never green.

## Adding content

Everything is append-only. To add a module, put one line in the `TRACKS` spec in `app/build_data.py`:

```python
"slug | Human Title | hours | tag1,critical"
```

then run:

```bash
python app/build_data.py
```

That regenerates both `.json` (source of truth) and `.js` (what the app loads from `file://`). Flashcards/drills/problems are written as per-module fragments under `app/data/{cards,drillsets,problemsets}/` and merged by id — fragments are validated at merge time, so a malformed row fails loudly instead of rendering blank in the app. **The app will not see new content until this runs.** Or just say `/tutor-add` and Claude does it.

---

## Local stack for labs

No paid cloud, ever.

```bash
# LLMs
ollama pull llama3.2  &&  ollama pull nomic-embed-text

# Data stores
docker run -d -p 5432:5432 -e POSTGRES_PASSWORD=dev pgvector/pgvector:pg17
docker run -d -p 27017:27017 mongo:7
docker run -d -p 6333:6333 qdrant/qdrant
docker run -d -p 8123:8123 -p 9000:9000 clickhouse/clickhouse-server
docker run -d -p 6379:6379 redis:7

# AWS APIs without an AWS bill
docker run -d -p 4566:4566 localstack/localstack
```

GPU labs (transformer training, LoRA fine-tuning) run on your local GPU or Google Colab free tier. Each such lab states which it assumes and how to shrink it.

---

## Keeping it current

The cloud and agent stacks move monthly. Say **"update"** and `/tutor-update` reads the watermark in `clouds/*/changelog/LAST_UPDATED.json`, pulls only what changed since, appends dated changelog entries, patches affected pages, and bumps the marker. Nothing is re-fetched or rewritten.

Want it automatic? Ask Claude to schedule it — weekly Saturday morning pairs with the weekend cadence.

---

## Quality bar

Every deep dive follows one format: **the 30-second version → why it gets asked → lineage (past → present → future) → mental model → how it actually works → build it from scratch → how it's done in production → tradeoffs and when NOT to → 10-20 interview questions with follow-up traps → red flags that fail you → cheat card**.

The exemplar is `curriculum/21-architecture-principles/06-resilience-catalogue.md` with its matching lab at `labs/py/01-circuit-breaker/`. If a new module is thinner than that, it isn't finished.
