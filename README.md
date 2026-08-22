# AI Tutor Service

Personal interview-and-mastery system for **Hari Siva Rami Dwarampudi** — Principal AI Engineer, actively interviewing.

**34 tracks · 390 modules · 891 hours** — with a **29-module, 79-hour, 9-weekend sprint** on top that's what actually decides your next loop. Fully local, free tier, zero cloud spend.

---

## Open it

```
C:\Users\medic\OneDrive\Documents\ai-tutor-service\app\index.html
```

Double-click. No server, no build step, no install. State saves to your browser; export it from the **Save/Load** tab into `progress/progress.json` to version it or move machines.

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
| `/tutor-add <thing>` | Appends new content and reindexes the app |
| **`/tutor-company`** | **Paste a job description → researched prep pack + role-play as that company's interviewer** |
| **`/tutor-debrief`** | **Report back after a real interview → it logs the questions, diagnoses the failure type, and re-prioritises the curriculum automatically** |

All twelve live in `skills/` and are installed to your account, so they work in any session, not just this folder. After editing one:

```powershell
powershell -ExecutionPolicy Bypass -File skills\install.ps1
```

The last two close the loop: prep against a real JD → interview → debrief → the plan updates itself from real evidence. Any topic asked in two or more interviews gets auto-promoted into the sprint.

---

## Layout

```
PLAN.md          the contract — tracks, roadmap, build phases
ROADMAP.md       weekend-by-weekend schedule
skills/          the 12 /tutor-* skills (source of truth) + install.ps1
app/             the gamified tutor (index.html + engine + generated data)
curriculum/      theory — deep dives, one .md per concept, 31 tracks
clouds/          AWS · Azure · GCP service atlases + changelogs
  CROSS-CLOUD-MAP.md    the equivalence table to recite in interviews
labs/            practice — py · java · go · rust · ts · infra, all test-driven
cheatsheets/     one-pagers for the morning of an interview
drills/          question banks
mocks/           your scored transcripts
progress/        exported state
```

---

## Three tiers

**SPRINT** — 29 modules, 79h, 9 weekends. Weekend-ordered and the quest generator follows that order exactly. Agent loops, LangGraph durability, RAG retrieval, context engineering, attention + inference serving, design craft (estimation/diagramming/method), eval, MVCC, your resume systems, and a zero-to-production capstone. This is the plan.

**Phase A — core.** Everything else you'd be embarrassed not to know for these roles: DSA + graph algorithms, **networking & protocols (TCP, gRPC, HTTP semantics, curl)**, **auth & appsec (JWT, OAuth2/OIDC)**, data engineering + EMR, testing, Docker/Kubernetes/Git/debugging, AI-assisted architecture, the AWS atlas.

**Phase B — mastery.** Computer systems from transistor to runtime, **reinforcement learning from MDPs to PPO**, Rust, classical ML and deep learning from scratch, quant finance and Basel, blockchain, quantum, frontier AI (world models, JEPA, Cosmos, robotics).

The app handles the sequencing. Sprint modules bypass prerequisite gating — if it's in the sprint you need it now.

**891 hours is well over two years of weekends, and that's intentional.** It's a reference library with a sprint on top, not a queue to drain. Do the sprint; pull on the rest when a topic comes up.

---

## Gamification

XP per activity → 10 levels (Initiate → **Principal Architect**) · weekend streaks · 42 badges · SM-2 spaced repetition · prereq-gated skill tree · boss battles every ~12 modules.

The spaced repetition matters more than it sounds for a weekend-only cadence: you forget between sessions, and the scheduler is what stops that.

---

## Adding content

Everything is append-only. To add a module, put one line in the `TRACKS` spec in `app/build_data.py`:

```python
"slug | Human Title | hours | tag1,critical"
```

then run:

```bash
python app/build_data.py
```

That regenerates both `.json` (source of truth) and `.js` (what the app loads from `file://`). **The app will not see new content until this runs.** Or just say `/tutor-add` and Claude does it.

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
