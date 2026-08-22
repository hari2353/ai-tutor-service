# Agent Memory: Working, Episodic, Semantic, Procedural

> **Track:** T07 Agentic AI · **Time:** 3h · **Prereqs:** `T07-agent-loop-from-scratch` · **Updated:** 2026-07-26
> **Module id:** `T07-agent-memory` · **Tags:** sprint (W4), memory

## The 30-second version

The model is stateless, so "memory" is always a retrieval system you build, and it splits four ways by *what* is stored and *when* it is written: **working** memory is the context window itself, **episodic** memory is what happened on specific past runs, **semantic** memory is durable facts about the user and world, and **procedural** memory is how to do things — rules, skills, and prompt-level policy. The hard part is not storage, it is the **write policy** and the **retrieval ranking**: naive vector search over past conversation turns performs badly because dialogue turns are not self-contained, embeddings encode topic rather than truth, and nothing in cosine similarity knows that a fact was superseded three sessions ago. Every real memory design needs an answer to "how does a wrong memory die" — TTL, contradiction-triggered supersession, and decay — because stale memory does not merely fail to help, it actively degrades answers by injecting confident falsehoods the model has no way to doubt. And the honest production picture is far simpler than the literature: most shipped "agent memory" is a structured user-profile row, a short summary, and the last N turns, not a temporal knowledge graph.

## Why this gets asked

Because it is the cleanest separator between people who have read about agents and people who have operated them. Almost every candidate can describe the ReAct loop; far fewer can say what happens on session 12 when the user's stored preference is wrong. The interviewer has lived one of two specific incidents: (a) an agent that confidently told a customer something derived from a memory written six months earlier that was no longer true, and the support ticket landed on their desk, or (b) a memory store that leaked one tenant's facts into another tenant's context because the retrieval filter was applied after the vector search rather than before. They are probing for write discipline, invalidation, and scoping. At staff level they will also probe whether you can say "we don't need this" — because most products that ask for memory need personalisation, and personalisation is a database problem.

---

## Lineage: past → present → future

**What came before.** The first LLM-era memory was a Python list. LangChain's `ConversationBufferMemory` (2022) concatenated every turn into the prompt; `ConversationSummaryMemory` replaced the old turns with an LLM-generated summary; `ConversationBufferWindowMemory` kept the last *k*. All three are now deprecated (buffer memory has carried a deprecation notice since LangChain v0.3.1, with the migration path being LangGraph checkpointers for within-thread state and a `BaseStore` for cross-thread memory). The pain that killed them was mechanical and predictable: the buffer grew until it broke the window, and cost grew quadratically because you re-sent everything on every turn; the summary variant fixed cost and broke fidelity, because summarising a conversation loses precisely the specifics — account numbers, dates, exact wording of a constraint — that the next turn needed. The academically important precursors are **Generative Agents** (Park et al., 2023), which introduced a memory stream with an explicit retrieval score combining *recency, importance, and relevance* plus periodic "reflection" that synthesised higher-level observations, and **MemGPT** (Packer et al., arXiv:2310.08560, Oct 2023), which reframed the whole thing as virtual memory management: an OS-style hierarchy where the model itself pages facts between a small in-context "main memory" and a large external store using function calls. MemGPT is why modern systems let the *model* edit its own memory rather than only letting the harness write to it.

**Where it stands now.** Three things are settled and one thing is genuinely contested. Settled: (1) the four-type taxonomy — working / episodic / semantic / procedural — is the common vocabulary and is what interviewers expect you to name; (2) memory writes must be *selective*, produced by an extraction step that decides ADD / UPDATE / DELETE / NOOP rather than dumping turns into a vector index; (3) retrieval must be hybrid — metadata prefilter, then semantic, then a recency/importance-weighted rerank — because pure cosine similarity over dialogue is weak. Contested: **what the storage substrate should be.** The extraction-and-facts camp (Mem0) argues you should distil conversations into short atomic facts, and reports a 26% relative uplift in LLM-as-judge score over OpenAI's built-in memory on the LOCOMO benchmark (66.9% vs 52.9%), with p95 latency of 1.44s vs 17.12s for full-context and roughly 1.8K tokens per conversation instead of 26K. The temporal-graph camp (Zep/Graphiti) argues facts need a time dimension and bi-temporal validity so you can answer "what did the user believe in March", and reports 94.8% on the MemGPT-era DMR benchmark against 93.4%, plus up to 18.5% accuracy improvement on the more realistic LongMemEval with ~90% lower latency than a full-context baseline. Each side benchmarks favourably against the other, which is your cue to distrust both numbers: Mem0's paper reports Zep's memory footprint at over 600,000 tokens per conversation versus Mem0's 1,764, a comparison Zep disputes. Meanwhile the model vendors moved in: Anthropic shipped a file-based **memory tool** plus **context editing** on 29 Sept 2025, and reported that memory + context editing together improved agentic-search performance 39% over baseline while context editing alone gave 29%. LangMem exists but remains pre-1.0 (0.0.30, Oct 2025) and is best understood as the LangGraph-native option rather than the strongest one. **The thing nobody advertises:** the median production system in mid-2026 is a Postgres table of user attributes, a rolling session summary, and last-N-turns. That is not a failure of ambition, it is usually correct, and saying so out loud is a senior signal.

**Where it's heading.** High confidence: **memory as a filesystem the agent edits with tools** is winning over memory as an opaque retrieval service, because files are inspectable, diffable, permissioned with tools you already have, and survive compaction. Anthropic's memory tool, Claude Code's `CLAUDE.md`, and Letta's memory blocks are the same idea from three directions. Medium confidence: **asynchronous consolidation** — Letta's "sleep-time compute", where an idle background turn reorganises memory instead of doing it inline on the user's latency budget — becomes standard, because doing extraction synchronously is the main reason memory systems feel slow. Lower confidence and explicitly speculative: **model-native memory**, where weights or a learned KV state hold user-specific adaptation, removing the retrieval layer entirely; there are research systems but nothing you should design around. Also speculative: consolidation of the vendor space. The memory-layer market in 2026 looks like the vector-DB market in 2022 — a dozen products each solving one third of the problem, active benchmark wars, and a consolidation wave that has not arrived yet. Do not couple your domain logic to any one of them.

---

## Mental model

Two axes: **timescale** (how long it lives) and **content type** (what kind of thing it is). Everyone remembers the four boxes if they map them onto a machine.

```
                     ┌──────────────────────────────────────────────────┐
   IN CONTEXT        │  WORKING MEMORY = the prompt you are sending      │
   (volatile,        │  system prompt · task · last N turns · tool out   │
    seconds-mins)    │  ceiling = context window · cost = every turn     │
                     └───────────────────▲──────────────────────────────┘
                                         │  retrieve (k small, ranked)
                    ┌────────────────────┴───────────────────────────────┐
                    │                                                    │
        ┌───────────┴──────────┐  ┌────────────┴─────────┐  ┌────────────┴──────────┐
        │ EPISODIC             │  │ SEMANTIC             │  │ PROCEDURAL            │
        │ "what happened"      │  │ "what is true"        │  │ "how to act"          │
        │ (run, trajectory,    │  │ (user prefers metric, │  │ (always confirm before │
        │  outcome, cost)      │  │  acct tier = gold)    │  │  refunds > $500)      │
        │ append-only log      │  │ upsert w/ conflicts   │  │ rules + skills files  │
        │ key: task signature  │  │ key: (tenant,user,    │  │ key: tool / situation │
        │ decays fast          │  │       predicate)       │  │ changes slowly        │
        └──────────────────────┘  └──────────────────────┘  └───────────────────────┘
                    ▲                       ▲                          ▲
                    └────── WRITE PATH: gate → dedupe → resolve ────────┘
                             conflict → supersede (never silent overwrite)
```

The analogy that lands in an interview: **working memory is RAM, episodic is the append-only write-ahead log, semantic is the indexed table, procedural is the stored procedures and config.** RAM is wiped every turn. The other three are yours to maintain, and like any database they need a schema, a write path, an invalidation story, and a tenancy boundary.

The second thing to internalise: **memory is a *precision* problem, not a recall problem.** You are injecting 5-15 items into a prompt that will be treated as authoritative. One wrong item is worse than ten missing ones, because a missing memory produces a clarifying question and a wrong memory produces a confident error.

---

## How it actually works

### The four types, concretely

| Type | Timescale | Written by | Read by | Storage | Invalidation |
|---|---|---|---|---|---|
| **Working** | this turn | the harness, every turn | the model, implicitly | the messages array | truncation / compaction |
| **Episodic** | days-weeks | end of run | few-shot selector, "have I done this before" | append-only rows (Postgres/SQLite + embedding col) | TTL 30-90d, decay by age |
| **Semantic** | months-years | extraction step | prefiltered retrieval on every turn | key-value + vector, or graph | contradiction → supersede; TTL by predicate class |
| **Procedural** | quarters | humans mostly, agents rarely | prompt assembly, always-on | files under version control | code review |

The most common design error is collapsing episodic and semantic into one vector index. They have different keys (task signature vs subject-predicate), different read patterns (rare and exemplar-shaped vs every-turn and fact-shaped), different decay rates, and different failure modes. One index means you retrieve a stale trajectory when you wanted a fact.

### Working memory: buffer vs summary vs vector-backed

This is the question actually asked in interviews, usually as "how do you handle a long conversation".

| Strategy | Tokens at turn *n* | Fidelity | Failure mode you'd observe |
|---|---|---|---|
| **Full buffer** | O(n²) cumulative spend | perfect | 40 turns in, either a 400 context-length error or the "lost in the middle" quality cliff before it |
| **Window (last k)** | O(k) | perfect recent, zero old | agent re-asks a question answered at turn 2 |
| **Rolling summary** | O(1) | lossy on specifics | agent says "your order" but has lost the order id; numbers and IDs are what summaries drop first |
| **Summary + window (hybrid)** | O(k) + const | good | the standard choice; still drops anything the summariser judged unimportant |
| **Vector-backed recall over turns** | O(k_retrieved) | erratic | retrieves a semantically similar but wrong turn; see below for why |
| **Externalised (files/store)** | O(pointer) | perfect, on demand | agent forgets to re-read; needs a prompt-level obligation to check the file |

The defensible default is **hybrid + externalisation**: summary of the old, verbatim recent window, IDs and constraints pinned in a structured block that never gets summarised, plus a scratchpad file for anything long. The pinned block matters more than it sounds: put `order_id`, `account_tier`, `deadline`, and open obligations in a small, stable, machine-generated `<state>` block, and the summariser can never lose them because it never touches them.

Token accounting, because you should be able to do it live:

```python
# Rough working-memory budget for a 200k window. Numbers are the shape, not gospel.
BUDGET = {
    "system_prompt":        1_500,   # stable → cache it
    "tool_schemas":         3_000,   # stable → cache it
    "procedural_rules":     1_000,   # stable → cache it
    "pinned_state_block":     300,   # regenerated each turn, tiny
    "retrieved_semantic":   1_200,   # ~8 facts × ~150 tok
    "retrieved_episodic":   1_500,   # 1-2 exemplars
    "rolling_summary":      2_000,
    "recent_turns_verbatim": 20_000, # the actual working set
    "headroom_for_output":  8_000,
}
# = ~38.5k of 200k. If you are anywhere near the window, you have a design bug,
# not a capacity problem. The first 5.5k is cacheable → ~90% cheaper on cache read.
```

### Episodic memory: implementation

Episodic memory answers "have I done something like this before, and how did it go". The key insight is that the retrieval key is the **task signature**, not the conversation text, and that you must store the *outcome* or you will happily retrieve a past failure as an exemplar.

```python
# episodic.py  — untested sketch, but the shape is what matters
import json, sqlite3, time, hashlib

SCHEMA = """
CREATE TABLE IF NOT EXISTS episodes (
  id            TEXT PRIMARY KEY,
  tenant_id     TEXT NOT NULL,
  user_id       TEXT NOT NULL,
  task_sig      TEXT NOT NULL,      -- normalised task descriptor, e.g. "refund:>500:eu"
  task_text     TEXT NOT NULL,
  plan          TEXT NOT NULL,      -- JSON list of (tool, args) actually taken
  outcome       TEXT NOT NULL,      -- 'success' | 'failure' | 'abandoned'
  outcome_note  TEXT,               -- why it failed, in one sentence
  steps         INTEGER,
  cost_usd      REAL,
  created_at    REAL NOT NULL,
  embedding     BLOB                -- of task_text, for fuzzy signature match
);
CREATE INDEX IF NOT EXISTS idx_ep_lookup ON episodes(tenant_id, user_id, task_sig, created_at);
"""

def write_episode(db, *, tenant, user, task_text, task_sig, plan, outcome,
                  note, steps, cost, embed):
    # WRITE POLICY: only episodes that are informative. Successes that took the
    # obvious path teach nothing; failures always teach something.
    informative = outcome == "failure" or steps >= 4 or _novel_toolset(plan)
    if not informative:
        return None
    eid = hashlib.sha256(f"{tenant}{user}{task_sig}{time.time()}".encode()).hexdigest()[:16]
    db.execute(
        "INSERT INTO episodes VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (eid, tenant, user, task_sig, task_text, json.dumps(plan), outcome,
         note, steps, cost, time.time(), embed),
    )
    db.commit()
    return eid

def recall_episodes(db, *, tenant, user, task_sig, k=2, max_age_days=90):
    """Exact-signature first, then fuzzy. Prefer successes; include ONE failure
    as an explicit anti-example, because 'do not do X again' is high-value."""
    cutoff = time.time() - max_age_days * 86400
    rows = db.execute(
        """SELECT task_text, plan, outcome, outcome_note, steps FROM episodes
           WHERE tenant_id=? AND user_id=? AND task_sig=? AND created_at>?
           ORDER BY (outcome='success') DESC, created_at DESC LIMIT ?""",
        (tenant, user, task_sig, cutoff, k + 1),
    ).fetchall()
    return rows
```

The **anti-example** trick is worth stating in an interview: injecting one past failure labelled as a failure, with the one-line reason, measurably reduces repeat failures more than injecting two more successes. It is also the cheapest form of learning an agent can do without touching weights.

### Semantic memory: extraction, upsert, and conflict

Semantic memory is where the damage happens, so this is where the engineering goes. The pipeline has four stages and skipping any of them is a known incident.

```
turn(s) ──▶ (1) CANDIDATE EXTRACTION ──▶ (2) GATE ──▶ (3) DEDUPE/RESOLVE ──▶ (4) COMMIT
             cheap model, structured      is it        does it contradict     with provenance,
             output, atomic claims        worth        anything stored?       validity window,
                                         keeping?      → ADD/UPDATE/          confidence
                                                         DELETE/NOOP
```

```python
# semantic.py — the decision the extraction step must return
from dataclasses import dataclass
from typing import Literal

@dataclass
class Fact:
    subject: str        # "user" | "account:1234" | "project:acme"
    predicate: str      # "prefers_units" | "timezone" | "primary_language"
    value: str          # "metric"
    confidence: float   # 0-1, from the extractor
    source_turn: str    # provenance: the exact quote that justified it
    valid_from: float   # event time
    valid_to: float | None = None   # bi-temporal: None = still believed
    ttl_days: int | None = None     # class-dependent, see table below

Decision = Literal["ADD", "UPDATE", "DELETE", "NOOP"]

EXTRACTION_PROMPT = """\
From the exchange below, extract ONLY durable facts about the user or their
account that would change how you answer a FUTURE, UNRELATED question.

Extract:  stable preferences, identity/role, constraints, entitlements, decisions made.
Do NOT extract:  anything task-local, anything inferable from the current request,
anything about the assistant, anything you are not >0.7 confident the user asserted,
anything transient ("I'm in a hurry today").

For each fact emit {subject, predicate, value, confidence, source_quote}.
Emit an empty list if nothing qualifies. An empty list is the correct and
most common answer.
"""
```

That last line is the whole write policy. **The default write decision is NOOP.** A memory system that stores something from 80% of turns has built a noise generator. Anchor on: fewer than 1 durable fact per 10 turns for most assistants, and a hard ceiling on facts per user (200-500 is generous) that forces eviction and thereby forces you to have an eviction policy.

Conflict resolution, which is the part candidates skip:

```python
def resolve(existing: Fact | None, new: Fact, now: float) -> tuple[Decision, Fact | None]:
    if existing is None:
        return "ADD", new
    if existing.value == new.value:
        # reinforcement: bump confidence + refresh recency, do not duplicate
        existing.confidence = min(1.0, existing.confidence + 0.1)
        return "NOOP", existing
    # genuine contradiction on the same (subject, predicate)
    if new.confidence < existing.confidence - 0.2 and new.valid_from < existing.valid_from:
        return "NOOP", existing              # weaker AND older → ignore
    # SUPERSEDE, do not overwrite. Close the old validity window, insert the new.
    existing.valid_to = now
    return "UPDATE", new
```

**Never hard-delete on contradiction.** Close `valid_to` and insert the new row. You need the history for three reasons: debugging ("why did it say gold tier?"), temporal questions ("what plan was I on in March?"), and audit. This is exactly the bi-temporal model Zep's Graphiti formalises — an event time and an ingestion time — and you can describe it without adopting Zep.

### Procedural memory

Procedural memory is the one people forget exists, and it is the one that produces the most value per token. It is the accumulated *how*: "always call `check_entitlement` before `issue_refund`", "this customer's API returns dates as DD/MM", "prefer `search_internal` over `search_web` for policy questions".

Three implementations, in increasing order of ambition:

1. **Static rules in the system prompt, under version control.** `AGENTS.md` / `CLAUDE.md` / a `rules/*.md` directory. Boring, reviewable, effective, and what you should do first. It is procedural memory whether or not you call it that.
2. **Learned rules with human approval.** The agent proposes a rule after a failure ("I called `issue_refund` without checking entitlement and it 403'd; propose rule R"), a human approves, the rule lands in the file via a PR. This is the highest-value pattern and almost nobody does it.
3. **Self-editing skills.** The agent writes reusable procedures (a script, a saved plan) and calls them later. Powerful, and the place where an unreviewed bad procedure becomes a persistent bug that reproduces on every future run.

The reason to keep procedural memory in **files under review** rather than in a vector store is blast radius. A wrong semantic fact affects one user. A wrong procedural rule affects every run, silently, until someone reads the prompt.

### Retrieval ranking: why naive vector recall over past turns performs badly

This is the highest-signal thing in the module. Say all five reasons.

1. **Dialogue turns are not self-contained.** "Yes, do that one" embeds nowhere near anything useful and is meaningless out of context. Chunking a conversation the way you'd chunk a document produces chunks whose meaning lives in their neighbours. Facts extracted into standalone sentences ("The user prefers metric units") retrieve well; raw turns do not.
2. **Embeddings encode topic, not truth or currency.** "I want to cancel my subscription" and "I decided not to cancel" are nearest neighbours. Cosine similarity has no notion of negation, supersession, or which one happened later. This is the mechanism behind the classic incident: the agent retrieves the *cancellation intent* turn and not the *retraction*.
3. **Precision collapses with volume.** With 50,000 stored turns and k=8, you are choosing 8 items out of 50k on a weak signal. Chroma's 2025 context-rot work is the general version of this: accuracy on needle-retrieval tasks drops 20-50% between 10k and 100k+ input tokens across 18 frontier models, and **distractors that are semantically near the answer hurt disproportionately** — which is exactly what a vector store returns by construction.
4. **No temporal reasoning.** "How long have I been a customer", "what did I decide last time", "has this changed" are all unanswerable by similarity. You need timestamps in the index and in the ranking.
5. **The retrieved items are treated as authoritative.** Unlike RAG over documents, where a bad chunk is usually visibly irrelevant, a bad *memory* reads as something the assistant knows about you. The model will not doubt it.

The fix is a four-term score plus a hard prefilter, and the prefilter is the security-relevant part:

```python
import math

def score(item, query_emb, now, *, w=(0.55, 0.20, 0.15, 0.10), half_life_days=None):
    """Generative-Agents-style composite: relevance + recency + importance + usage."""
    ws, wr, wi, wu = w
    relevance = cosine(item.embedding, query_emb)                    # 0-1
    hl = half_life_days or CLASS_HALF_LIFE[item.predicate_class]      # per-class decay
    age_days = (now - item.valid_from) / 86400
    recency = 0.5 ** (age_days / hl)                                 # exponential decay
    importance = item.importance                                     # 0-1, set at write
    usage = math.log1p(item.hit_count) / math.log1p(50)              # capped
    return ws*relevance + wr*recency + wi*importance + wu*usage

def retrieve(store, query, *, tenant, user, k=8, floor=0.35):
    # 1. HARD PREFILTER FIRST — tenancy and validity, in the query, not after.
    candidates = store.query(
        filters={"tenant_id": tenant, "user_id": user, "valid_to": None},
        vector=embed(query), top_n=50,           # over-fetch for reranking
    )
    # 2. Composite rank
    ranked = sorted(candidates, key=lambda i: -score(i, embed(query), now()))
    # 3. Floor: returning nothing is a valid, often correct answer
    kept = [i for i in ranked[:k] if score(i, embed(query), now()) >= floor]
    # 4. Diversity: never two facts with the same predicate
    seen, out = set(), []
    for i in kept:
        if i.predicate in seen:
            continue
        seen.add(i.predicate); out.append(i)
    return out
```

Four details that separate this from the naive version:

- **Prefilter before the vector search, not after.** If you post-filter, a tenant with many similar facts can crowd out the correct tenant's facts from the top-50, and worse, a bug in the post-filter is a cross-tenant data leak. Every vector store supports pre-filtered ANN; use it.
- **A relevance floor.** Returning zero memories is correct most of the time. Systems without a floor always inject *something*, and that something is noise on unrelated turns.
- **Predicate-level diversity.** Otherwise five near-duplicate paraphrases of the same preference eat the whole budget.
- **Render with provenance and dates.** Inject as `[2026-03-04, conf 0.9] user prefers metric units` rather than a bare sentence. The model handles a dated, confidence-tagged claim more carefully than an undated assertion, and you get a debuggable trace for free.

### Forgetting and decay

"How does a wrong memory die?" If your design review cannot answer that, it is not done. Four mechanisms, and you need more than one:

| Mechanism | Trigger | Applies to |
|---|---|---|
| **TTL by predicate class** | age > class TTL | everything; see table |
| **Contradiction supersession** | new fact conflicts | semantic (close `valid_to`) |
| **Decay in ranking** | continuous | everything (soft forgetting — cheaper and safer than deletion) |
| **Capacity eviction** | facts_per_user > cap | lowest composite score wins eviction |
| **User/regulatory deletion** | explicit request, GDPR Art. 17 | hard delete + tombstone, cascading to embeddings and derived summaries |

Class TTLs, as a starting point you can defend:

```python
CLASS_TTL_DAYS = {
    "identity":        None,   # name, language — no expiry, but supersedable
    "stable_pref":     365,    # units, tone, format
    "entitlement":      30,    # plan tier, quota — re-derive from source of truth instead!
    "project_state":    14,    # "working on the Q3 migration"
    "task_local":        0,    # never persist; this is a working-memory item
}
CLASS_HALF_LIFE = {"identity": 3650, "stable_pref": 180, "entitlement": 14,
                   "project_state": 7, "task_local": 1}
```

The `entitlement` row carries the most important lesson: **anything that has a system of record should be read from the system of record, not remembered.** Plan tier, balance, open ticket count, feature flags — all of these are one API call away and all of them go stale in memory. Remembering them is how you build an agent that tells a downgraded customer they still have premium support. Memory is for things with no other home: preferences, decisions, context the user gave you in prose.

Soft forgetting deserves a note. Deletion is irreversible and loses audit; decay is reversible and self-correcting. Prefer decay plus a floor, and reserve hard delete for user requests and legal obligation.

### Cross-session user identity

Memory is only useful if you can find the right person's memory, which makes identity a load-bearing part of the design.

```
memory key = (tenant_id, subject_id, namespace)
   tenant_id   — hard isolation boundary. Separate index/collection per tenant if
                 your store supports it; at minimum a mandatory prefilter that
                 cannot be omitted (enforce in a repository layer, not at call sites).
   subject_id  — the stable identity. NOT the session id, NOT the device id.
   namespace   — "semantic" | "episodic" | "procedural" | app-specific scope
```

The failure modes, in order of how often they happen:

- **Anonymous-to-known merge.** A user chats anonymously, then logs in. You now have two memory subjects. You must merge, and merge is where you either lose facts or import facts from a shared kiosk device into someone's private profile. Rule: merge anonymous → known only on an explicit authentication event, never on a heuristic device match, and record the merge in provenance so it can be undone.
- **Shared accounts.** One `user_id`, two humans, contradictory preferences. Symptom: the composite score oscillates between two clusters of facts and the agent's behaviour appears random across sessions. Mitigation: allow contradictory facts to coexist when both have recent reinforcement, and surface the ambiguity ("last time you preferred X, is that still right?") rather than silently picking.
- **Cross-tenant leak.** Post-filtering, a missing filter on one code path, or a shared embedding cache keyed only by text. Symptom you would actually see: a memory injected into the prompt whose `source_turn` provenance references a conversation id that does not belong to the current tenant. That is why provenance is not optional — it makes the leak detectable in a log rather than only in a customer complaint.
- **Scope creep across products.** Facts learned in the support agent leaking into the sales agent. Sometimes desirable, usually a consent problem. Namespace explicitly and require an opt-in to read across namespaces.

---

## Build it from scratch

The lab at `(lab pending)` builds all four stores against SQLite plus a local embedding model, with a scripted fake LLM so the tests are deterministic:

1. **Working memory** — buffer, window, summary, hybrid. Assert the pinned `<state>` block survives 50 turns of summarisation while a naive summariser loses the order id. This single test is the module's thesis.
2. **Episodic store** — the schema above, the informativeness gate, and recall by task signature. Assert that a past *failure* is retrieved and labelled as an anti-example.
3. **Semantic store** — extraction → gate → resolve → commit, with bi-temporal `valid_from`/`valid_to`. Assert supersession: after "I moved to Berlin", the Munich fact is closed, not deleted, and a query for "where did I live in January" still answers correctly.
4. **Retrieval ranking** — implement the four-term score. Then build the adversarial test: 5,000 synthetic facts, one of which is the retracted cancellation. Show that pure cosine retrieves the wrong one and the composite score with recency decay does not. Measure precision@8 both ways.
5. **Decay and eviction** — class TTLs, capacity cap, and a `forget(user_id)` that cascades to embeddings, derived summaries, and episodic rows.
6. **Tenancy** — a repository layer where it is impossible to issue an unfiltered query, plus a test that fails if a raw query bypasses it.

Do step 4 even if you skip everything else. "I built the adversarial retrieval test and pure vector search lost" is a sentence that ends the memory portion of an interview in your favour.

---

## How it's done in production

**The stack most people actually have.** Session state in the agent framework's checkpointer (LangGraph `AsyncPostgresSaver` or equivalent), a `user_profile` table in the primary database with typed columns for the handful of things that matter, a `memories` table with `(tenant_id, user_id, predicate, value, valid_from, valid_to, confidence, source)` and a pgvector column, and procedural rules in the repo. That is it. It is boring, it is auditable, it uses infrastructure your on-call already understands, and it beats a managed memory service for anything where the fact set is small and mostly structured.

**When you reach for a product:**

| Tool | Model | Buys you | Costs you |
|---|---|---|---|
| **Mem0** | LLM extraction → atomic facts across vector + graph + KV | fastest path to working memory, widest framework integrations, low token footprint (~1.8K/conversation in their LOCOMO run) | extraction is an LLM call in your write path; facts lose nuance; you inherit their schema |
| **Zep / Graphiti** | bi-temporal knowledge graph, episodes, entity + relation extraction | genuinely good temporal reasoning ("what was true in March"), structured + unstructured fusion | expensive graph construction; heavier operationally; the 600k-tokens-per-conversation figure is Mem0's measurement and disputed, but nobody claims Graphiti is cheap |
| **Letta (MemGPT)** | agent edits its own memory blocks via tools; sleep-time compute for async consolidation | the self-editing model, which is the right long-term shape; stateful-agent server | opinionated runtime; you adopt their agent abstraction, not just a memory layer |
| **LangMem** | LangGraph-native semantic/episodic/procedural helpers over `BaseStore` | least friction if you are already LangGraph | pre-1.0 (0.0.30, Oct 2025); thinner and less battle-tested than the above |
| **Anthropic memory tool + context editing** | model-side: file-based memory directory you host, plus automatic clearing of stale tool results | +39% on their internal agentic search eval (memory + context editing); +29% context editing alone; you own the storage backend | Claude-specific; the "memory" is files, so *you* still design the schema and write policy |

Note what the vendor numbers have in common: they are all measured on conversational-recall benchmarks (LOCOMO: ~300 turns, ~9K tokens, up to 35 sessions; LongMemEval-S: ~500 questions over ~115K-token histories). If your product is a 6-turn support chat with a known schema, none of those benchmarks describes your workload and none of those uplifts will transfer.

**Failure modes**

| Symptom | Cause | Fix |
|---|---|---|
| Agent asserts something outdated with full confidence | No invalidation; fact stored with no TTL and never superseded | Class TTLs + contradiction supersession + render dates into the prompt |
| Agent tells a downgraded user they have premium features | Entitlement was *remembered* instead of *read* | Never persist anything with a system of record; call the API |
| Quality got worse after enabling memory | Write policy too loose; noise injected on every turn | Relevance floor, per-predicate diversity, drop facts below confidence 0.7, measure with memory on/off A/B |
| Retrieves a retracted intent ("wants to cancel") | Pure cosine ranking, no recency, no supersession | Composite score with exponential recency decay; close `valid_to` on retraction |
| One tenant's facts appear in another's prompt | Filter applied *after* ANN search, or a code path missing the filter | Pre-filtered ANN, per-tenant namespaces, repository layer that cannot issue unfiltered queries |
| First token latency jumped 600ms+ | Synchronous extraction and/or embedding on the write path | Move extraction to a background task or a post-response hook; sleep-time consolidation |
| Behaviour randomly differs between sessions for the same user | Shared account, or contradictory facts with similar scores | Detect the contradiction, ask, don't guess |
| Memory store grew to millions of rows in a month | Storing turns instead of facts; no cap | Informativeness gate, per-user cap with score-based eviction |
| GDPR deletion request cannot be satisfied | Facts copied into derived summaries and embeddings with no lineage | Provenance on every row; deletion cascades to derived artefacts |
| Agent repeats a mistake it made last week | No episodic memory of failures | Store failures with a one-line reason; inject as an anti-example |

**Measure it or don't ship it.** The only honest evaluation of a memory system is an A/B with memory on and off on a golden set of *cross-session* tasks, plus a specific adversarial slice containing superseded facts. Track: task success delta, injected-memory precision (fraction of injected facts a human judges relevant and correct), tokens added per turn, and write rate (facts per 100 turns). If precision is under ~0.7, memory is hurting you and the fix is a stricter write gate, not a bigger *k*.

---

## Tradeoffs & when NOT to use it

- **If the task is single-session, do not build memory.** A summarised window is memory enough. Cross-session memory earns its complexity only when users return *and* the returning context is expensive for them to restate. If restating takes the user five seconds, a memory system is a net negative for everyone.
- **If the facts have a schema, use a table.** "Preferred language", "notification channel", "plan tier" are columns. A vector index over prose is a strictly worse way to store a known-cardinality enum: slower, fuzzier, unqueryable, and impossible to validate. Reach for embeddings only for the genuinely open-vocabulary residue.
- **If there is a system of record, read it.** Repeated because it is the most common design error. Memory is for facts with no other home.
- **In regulated or high-stakes domains, memory is a liability surface.** A remembered clinical or financial detail that is wrong, or that the user did not consent to persist, is worse than no memory. If you cannot produce an auditable "why did you believe that" trace with provenance and a date, do not persist.
- **Do not adopt a managed memory service to avoid designing memory.** The write policy, the invalidation rules, and the tenancy model are the actual work and every product makes you supply them. Adopting one before you know your fact schema means you inherit theirs.
- **Graph memory is usually premature.** It genuinely wins on multi-hop and temporal questions over long histories. If your questions are "what does this user prefer", a graph is expensive infrastructure for a key-value lookup, and the extraction cost lands on every write.
- **Prefer soft forgetting to hard deletion** everywhere except legal deletion. Decay is reversible and self-correcting; deletion loses your audit trail and your ability to answer temporal questions.

---

## Interview questions

### Q1 — What are the types of agent memory?
**Testing:** vocabulary, and whether you can go one level past the list.
**Answer:** Four. **Working** — the context window itself: system prompt, task, recent turns, tool output; volatile, re-sent every turn, bounded by the window. **Episodic** — what happened on past runs: task, trajectory, outcome, cost; append-only, keyed by task signature, decays in weeks. **Semantic** — durable facts about the user or world; upserted with conflict resolution, keyed by (subject, predicate), lives for months. **Procedural** — how to act: rules, skills, tool-ordering constraints; usually files under version control, changes on human timescales. They differ in write path, retrieval key, decay rate, and blast radius when wrong, which is why they should not share one index.
**Follow-up trap:** *"Which one do most teams get wrong?"* — procedural, because most teams don't recognise that their system prompt *is* procedural memory and therefore never version, review, or evaluate it. And it has the largest blast radius: a wrong semantic fact hurts one user, a wrong procedural rule hurts every run silently.

### Q2 — Design memory for a support agent that handles the same customers across many sessions.
**Testing:** the standard staff-level system design question on this topic.
**Answer:** Start from the access pattern: users return with follow-ups, need context from prior tickets, and the tenant boundary is hard. Four tiers. In-session: LangGraph checkpointer keyed by thread, hybrid summary + last-8-turns verbatim, plus a pinned `<state>` block holding ticket id, entitlement, and open obligations that the summariser never touches. Semantic: a `memories` table keyed `(tenant_id, user_id, predicate)` with `value, confidence, valid_from, valid_to, source_quote` and a pgvector column; written by a cheap extraction call that defaults to NOOP. Episodic: past ticket resolutions keyed by task signature, with outcomes, retrieved as one or two exemplars including one anti-example. Procedural: escalation and refund rules in the repo, reviewed. Retrieval: prefilter on tenant and `valid_to IS NULL` inside the ANN query, over-fetch 50, rerank on relevance/recency/importance/usage, apply a 0.35 floor and per-predicate diversity, cap at 8 items. Entitlement and ticket status are **not** memory — they are API reads. Deletion cascades from a provenance chain for GDPR.
**Follow-up trap:** *"How does a wrong memory die?"* — this is the question the whole thing is asked for. Answer: four mechanisms. Per-class TTL (entitlements 30d, project state 14d, stable preferences 365d, identity never). Contradiction supersession that closes `valid_to` rather than overwriting. Continuous decay in the ranking function so wrongness fades even without an explicit contradiction. Capacity eviction on the lowest composite score. Plus hard delete only on user request or legal obligation, cascading to embeddings and derived summaries.

### Q3 — Why does naive vector search over past conversation turns perform badly?
**Testing:** whether you have actually measured a memory system.
**Answer:** Five reasons. Turns are not self-contained, so a chunked conversation produces chunks whose meaning lived in their neighbours ("yes, do that one"). Embeddings encode topic, not truth or currency, so "I want to cancel" and "I decided not to cancel" are nearest neighbours. Precision collapses with volume: 8 items chosen from 50,000 on a weak signal, and Chroma's context-rot work shows near-miss distractors hurt disproportionately, which is exactly what ANN returns by construction. There is no temporal reasoning, so "what did I decide last time" is unanswerable by similarity. And injected memories are treated as authoritative, unlike a RAG chunk which is visibly irrelevant when wrong. The fix is extracting standalone facts instead of storing turns, plus hybrid retrieval: hard prefilter, over-fetch, composite rerank with recency decay, relevance floor.
**Follow-up trap:** *"Show me the ranking function."* — `0.55·cosine + 0.20·0.5^(age/half_life) + 0.15·importance + 0.10·log1p(hits)`, with a per-predicate-class half-life (entitlements ~14 days, stable preferences ~180). Weights are a hyperparameter you tune against a golden set, not a constant to memorise; the structure is the point.

### Q4 — What is worth writing to memory?
**Answer:** The gate is: would this change how I answer a *future, unrelated* question? That admits stable preferences, identity and role, hard constraints, entitlement decisions, and choices the user made. It excludes anything task-local, anything re-derivable from the current request, anything with a system of record, and anything under ~0.7 extraction confidence. The default decision is NOOP and the empty list is the most common correct extraction output. As a calibration: under one durable fact per ten turns for a typical assistant, plus a hard per-user cap in the low hundreds so eviction is forced to exist.
**Follow-up trap:** *"Your extractor writes something from 80% of turns. What's the observable consequence?"* — quality drops even though nothing errors. You'd see it as: injected-memory precision under 0.5, growing token cost per turn, and A/B results where memory-on loses on unrelated queries because five marginal facts crowd out the one that mattered. Memory is a precision problem: one wrong item is worse than ten missing ones, because a missing memory produces a clarifying question and a wrong memory produces a confident error.

### Q5 — Buffer, summary, or vector-backed working memory?
**Answer:** Hybrid, plus externalisation. Full buffer has perfect fidelity and quadratic cumulative cost, and degrades on quality via lost-in-the-middle before it hits the hard limit. Window is cheap and forgets turn 2. Pure rolling summary is O(1) and drops exactly the specifics you need — IDs, dates, exact constraint wording are the first casualties. So: rolling summary of the old turns, last k verbatim, a small machine-generated pinned state block for IDs and open obligations that the summariser never sees, and long artefacts written to files the agent re-reads on demand. Vector recall over your own turns is the weakest option for the reasons in Q3.
**Follow-up trap:** *"Prove the pinned block matters."* — the test: 50 turns, an order id mentioned once at turn 3, then summarise. A naive summariser loses the id roughly whenever the conversation topic has moved on; the pinned block cannot lose it because it is regenerated structurally from state rather than produced by a model.

### Q6 — Mem0 vs Zep vs Letta vs LangMem vs building it.
**Testing:** whether you evaluate tools or collect them.
**Answer:** Mem0 extracts atomic facts into vector + graph + KV; best ecosystem integration and low token footprint (they report ~1.8K tokens per conversation vs 26K full-context, 26% relative LLM-judge uplift over OpenAI's memory on LOCOMO at 66.9% vs 52.9%, and 91% lower p95 at 1.44s vs 17.12s). Zep/Graphiti builds a bi-temporal knowledge graph and genuinely wins temporal reasoning (94.8% vs 93.4% on DMR, up to 18.5% better on LongMemEval with ~90% lower latency than full-context), at meaningfully higher construction cost. Letta is the self-editing-memory model with async sleep-time consolidation, which I think is the right long-term shape, but you adopt their runtime. LangMem is the LangGraph-native option and still pre-1.0 at 0.0.30. And every vendor's benchmark shows them winning, which is the tell: Mem0's paper puts Zep at 600k+ tokens per conversation against Mem0's 1,764, Zep disputes it, and none of these benchmarks resembles a 6-turn support chat. For most products I would build it: a typed profile table, a small facts table with bi-temporal columns and pgvector, and rules in the repo.
**Follow-up trap:** *"So all these products are pointless?"* — no. Zep earns its keep when you have genuinely multi-hop temporal questions over long histories. Letta earns it when you want the agent to curate its own memory. But note what none of them supply: your write policy, your invalidation rules, and your tenancy model. Those are the actual work, and adopting a product before you know your fact schema means you inherit theirs.

### Q7 — Anthropic reported context editing gave 29% and memory plus context editing gave 39%. What does that tell you?
**Testing:** whether you read numbers or repeat them.
**Answer:** Two things. First, the bulk of the gain came from *removing* stale content, not adding recall — 29 of the 39 points. That is the counterintuitive core result: on long-horizon tool use, subtraction beats addition. Second, in the same 100-turn web-search eval, context editing cut token consumption 84% while enabling runs that previously failed on context exhaustion, so it is not a quality-for-cost trade, it is both. The caveat: this is an internal agentic-search eval with many tool results, which is the workload context editing is designed for. Do not quote 29% as a universal number.
**Follow-up trap:** *"Then why bother with a memory store at all?"* — because context editing is within-session. The extra 10 points came from information surviving *across* sessions. They solve different problems, and the numbers show which problem is bigger for long single runs.

### Q8 — Your agent gave a wrong answer because of a stored memory. Walk me through the incident.
**Testing:** debuggability, which is the whole argument for provenance.
**Answer:** First, the answer must be traceable: I need the exact injected memory block from that request in the trace, with each fact's `source_quote`, `valid_from`, `confidence`, and store id. Without that, this is unfalsifiable. With it: identify the offending fact, check whether it was wrong at write time (extraction bug — fix the gate, replay the extractor over a sample) or right-then-wrong-now (invalidation bug — the class TTL was too long, or a contradicting statement failed to supersede it). Then check whether it should have been memory at all; if it has a system of record, the fix is to delete the predicate class entirely and read the API. Finally, backfill: if the extraction bug is systemic, close `valid_to` on the whole affected predicate class rather than patching one row.
**Follow-up trap:** *"How would you have caught it before production?"* — an adversarial eval slice built specifically from superseded facts: for each golden task, plant a retracted or outdated fact that pure similarity would retrieve, and assert the composite ranking does not surface it. Plus injected-memory precision as a tracked metric with an alert under 0.7.

### Q9 — Where does episodic memory actually help?
**Answer:** Three places. Anti-examples: injecting one past *failure* with its one-line reason measurably reduces repeat failures, and it is the cheapest learning an agent can do without touching weights. Dynamic few-shot: retrieve a successful trajectory for the same task signature instead of shipping static exemplars, which keeps the prompt short and relevant. And cost/latency prediction: past step counts and spend for a task signature let you set a realistic budget for this run rather than one global cap. What it does *not* help with is knowledge — that is semantic memory, and mixing them in one index means you retrieve a stale trajectory when you wanted a fact.
**Follow-up trap:** *"How do you avoid retrieving a bad trajectory as a good example?"* — store the outcome and rank on it, never on similarity alone. Failure episodes are only ever injected explicitly labelled as anti-examples. And gate writes on informativeness: a two-step success down the obvious path teaches nothing and should not be stored.

### Q10 — How do you scope memory in a multi-tenant product?
**Answer:** The key is `(tenant_id, subject_id, namespace)` and the tenant filter goes *inside* the ANN query, not after it. Post-filtering is both a quality bug — the correct tenant's facts get crowded out of the top-50 by another tenant's near-duplicates — and a leak waiting for one code path to forget the filter. Enforce it structurally: a repository layer that cannot issue an unfiltered query, ideally with per-tenant namespaces or collections. Namespace by product surface too, and require an explicit opt-in to read across namespaces, because facts learned in support leaking into sales is a consent problem even when it is technically convenient.
**Follow-up trap:** *"A user chats anonymously then logs in. What happens to the anonymous memories?"* — merge only on an explicit authentication event, never on a device or fingerprint heuristic, because shared devices then import a stranger's facts into a private profile. Record the merge in provenance so it is reversible, and re-run the conflict resolver over the merged set rather than blind-appending.

### Q11 — Extraction on the write path added 600ms to your p50. Fix it.
**Answer:** Extraction and embedding do not belong in the request path. Move them to a post-response background task keyed on the conversation, or batch them at session end, or do them on an idle turn — Letta's sleep-time compute is the productised version of that idea. Consequence you must state: memory becomes eventually consistent, so a fact stated at turn 5 may not be retrievable at turn 6. Mitigate by keeping the current session's facts in working memory anyway (they are already in the recent-turns window), which means the async delay only affects cross-session recall where a few seconds is irrelevant. Also: use a small cheap model for extraction, and skip it entirely on turns that a keyword/heuristic prefilter says contain no candidate facts, which is most turns.
**Follow-up trap:** *"What breaks if the background job fails silently?"* — memory silently stops growing and nobody notices for weeks, because the agent still works, just without personalisation. You need a write-rate metric with an alert on a floor, not just an error rate. "Facts written per 1,000 turns dropped to zero" is the observable signal.

### Q12 — What is procedural memory and how do you update it safely?
**Answer:** It is the accumulated *how*: tool-ordering constraints, domain quirks, policy. In practice it lives in the system prompt or a rules directory, and the right implementation is files under version control. Safe update path: the agent *proposes* a rule after a failure, with the trace as evidence; a human approves; it lands via a PR and gets an eval run. Reason for the human gate: blast radius. A wrong semantic fact affects one user; a wrong procedural rule affects every run, silently, until someone reads the prompt.
**Follow-up trap:** *"Would you ever let the agent write procedural memory unattended?"* — only for narrow, verifiable, reversible things: a cached API quirk it can re-verify, a saved query it re-validates before use. Never for policy, permissions, or anything about money or destructive operations. And every self-written rule needs a timestamp and an expiry, or you accumulate cargo cult that nobody can trace the origin of.

### Q13 — Your VP wants "memory like ChatGPT". What do you actually build?
**Testing:** whether you can decline gracefully — the highest-value senior move here.
**Answer:** I'd ask which of three things they mean, because they have very different costs. If it is "the assistant should not re-ask my name and preferences", that is a typed profile table with maybe twenty predicates, an extraction step, and no vector store at all — days of work. If it is "it should recall specifics of a conversation from three months ago", that is a real semantic store with retrieval ranking and invalidation — weeks, plus an ongoing eval burden. If it is "it should get better at my codebase over time", that is procedural memory and progress files, which is mostly a prompt-and-files problem. I'd ship the first, instrument whether users hit the second, and be explicit that the second has a downside the first doesn't: it can be wrong out loud.
**Follow-up trap:** *"That sounds like you're avoiding the hard version."* — I'm sequencing it. The failure mode of shipping the hard version first is well documented: quality drops after enabling memory because the write policy was loose, and you cannot tell because you had no memory-off baseline. Ship the typed version, get the baseline, then add open-vocabulary facts behind an A/B with injected-memory precision as a gate.

### Q14 — What is bi-temporal memory and why would you need it?
**Answer:** Two independent time axes per fact: **event time** (when the fact became true in the world) and **ingestion time** (when the system learned it), plus a validity window `[valid_from, valid_to)`. You need it for three things: answering temporal questions correctly ("what plan was I on in March" needs the state as of March, not now), debugging ("the agent said gold tier because it learned that on 4 March from this quote"), and correct ordering when facts arrive out of order — a user telling you on Tuesday about something that changed last month should supersede a fact you learned on Monday about the state two months ago. Graphiti formalises this; you can implement the useful 80% with two timestamp columns and never hard-deleting on contradiction.
**Follow-up trap:** *"Isn't a `updated_at` column enough?"* — no, and the counterexample is exactly the out-of-order case: `updated_at` only records ingestion, so last-write-wins makes a stale-but-recently-ingested fact beat a fresh-but-earlier-ingested one. You also lose the ability to reconstruct historical state, which is what makes the "why did it say that" investigation possible at all.

### Q15 — Would you use a knowledge graph for memory?
**Answer:** Only for a specific question shape. Graphs win when queries are multi-hop over entities and relations ("which of my teammates worked on the service that broke last quarter") or genuinely temporal over long histories, and Zep's LongMemEval results are real evidence for that. They lose when the fact set is small, the predicates are known, and the query is a lookup — in which case you have paid for entity extraction, relation extraction, and graph maintenance on every write to replace a `SELECT`. My default is: typed columns for known predicates, a flat bi-temporal facts table with pgvector for the open-vocabulary residue, and a graph only after I can point at query traces that need multi-hop.
**Follow-up trap:** *"What's the hidden cost of graph memory?"* — write amplification and non-determinism at write time. Every ingestion runs extraction and reconciliation LLM calls, so cost scales with conversation volume rather than query volume, and a bad extraction corrupts structure rather than just adding a bad row — which is much harder to detect and to undo than a wrong value in a flat table.

---

## Red flags that fail you

- "We store the conversation in a vector DB and retrieve the relevant turns." No write policy, no ranking beyond cosine, no invalidation. This is the single most common wrong answer.
- No answer to "how does a wrong memory die".
- Remembering things that have a system of record — plan tier, balance, ticket status.
- Applying the tenant filter after the vector search.
- Treating "memory" and "RAG over docs" as the same problem. Memory is authoritative and about the user; a document chunk is evidence and visibly wrong when it is wrong.
- Naming the four memory types and then designing one undifferentiated store.
- Claiming a vendor's benchmark uplift will transfer to a workload that looks nothing like the benchmark.
- Hard-deleting on contradiction, losing the audit trail and the ability to answer temporal questions.
- No plan for evaluating whether memory helps — no memory-off baseline, no precision metric.
- Putting extraction on the request path and being surprised by the latency.

## Cheat card

```
FOUR TYPES (name all four, then differentiate)
  WORKING     = the prompt. volatile. re-sent every turn. bounded by window.
  EPISODIC    = past runs (task_sig, plan, OUTCOME, cost). append-only. TTL 30-90d.
  SEMANTIC    = facts (subject, predicate, value). upsert+supersede. months.
  PROCEDURAL  = rules/skills. files in git. biggest blast radius when wrong.
  different write path · retrieval key · decay rate · blast radius → different stores

WORKING MEMORY LADDER
  buffer O(n²) cost · window O(k) forgets · summary O(1) drops IDs/dates first
  → HYBRID: summary(old) + last-k verbatim + PINNED <state> block (IDs, obligations)
  → + externalise long artefacts to files; pinned block is never summarised

WRITE POLICY (default is NOOP)
  gate: "changes a FUTURE UNRELATED answer?" · conf >= 0.7 · no system-of-record facts
  target < 1 durable fact / 10 turns · hard per-user cap (200-500) forces eviction
  decisions: ADD / UPDATE(supersede) / DELETE / NOOP

RETRIEVAL RANK (say the formula)
  0.55·cosine + 0.20·0.5^(age/half_life) + 0.15·importance + 0.10·log1p(hits)
  PREFILTER (tenant, valid_to IS NULL) INSIDE the ANN query, never after
  over-fetch 50 → rerank → floor 0.35 → per-predicate diversity → k<=8
  render as: [2026-03-04, conf 0.9] <fact>   ← dates+provenance make it debuggable

WHY NAIVE VECTOR RECALL FAILS (5)
  turns not self-contained · embeddings = topic not truth ("cancel" ~ "not cancel")
  precision collapses at volume · no temporal reasoning · injected = authoritative

FORGETTING (need >1 mechanism)
  class TTL: identity ∞ · stable_pref 365d · entitlement 30d · project 14d · task 0
  contradiction → close valid_to (NEVER hard overwrite) · decay in ranking
  capacity eviction on lowest score · hard delete only for user/GDPR, cascade derived

BI-TEMPORAL = event_time + ingestion_time + [valid_from, valid_to)
  updated_at alone loses out-of-order supersession and historical reconstruction

NUMBERS
  Mem0 LOCOMO: 66.9% vs 52.9% (26% rel) · p95 1.44s vs 17.12s · 1.8K vs 26K tok
  Zep: DMR 94.8 vs 93.4 · LongMemEval +18.5% acc, ~90% lower latency
  Anthropic 2025-09-29: memory+context editing +39% · context editing alone +29%
  context rot: 20-50% accuracy drop 10k→100k+ tokens across 18 frontier models
  LangMem still pre-1.0 (0.0.30) · ConversationBufferMemory deprecated LC v0.3.1

WHEN NOT TO
  single-session → summarised window is enough
  facts have a schema → use typed columns, not embeddings
  system of record exists → CALL THE API, never remember it
  regulated domain w/o provenance trail → don't persist
  graph before you have multi-hop query traces → premature

EVAL OR DON'T SHIP
  A/B memory on/off on CROSS-SESSION golden tasks + adversarial superseded-fact slice
  track: injected-memory precision (alert < 0.7) · tokens added/turn · writes/1k turns
```

## Sources

- [Anthropic — Managing context on the Claude Developer Platform](https://claude.com/blog/context-management) — memory tool + context editing, the 39% / 29% / 84% figures, published 2025-09-29; accessed 2026-07-26
- [MemGPT: Towards LLMs as Operating Systems](https://arxiv.org/abs/2310.08560) — Packer et al., 2023; self-editing memory, OS-style paging; accessed 2026-07-26
- [Generative Agents: Interactive Simulacra of Human Behavior](https://arxiv.org/abs/2304.03442) — Park et al., 2023; the recency/importance/relevance retrieval score and reflection; accessed 2026-07-26
- [Mem0: Building Production-Ready AI Agents with Scalable Long-Term Memory](https://arxiv.org/abs/2504.19413) — LOCOMO figures (66.9% vs 52.9%, 1.44s vs 17.12s p95, ~1.8K vs 26K tokens); accessed 2026-07-26
- [Zep: A Temporal Knowledge Graph Architecture for Agent Memory](https://arxiv.org/abs/2501.13956) — DMR 94.8%, LongMemEval up to +18.5%, bi-temporal model; accessed 2026-07-26
- [Evaluating Very Long-Term Conversational Memory of LLM Agents (LOCOMO)](https://arxiv.org/abs/2402.17753) — benchmark shape: ~300 turns, ~9K tokens, up to 35 sessions; accessed 2026-07-26
- [Chroma — Context Rot: How Increasing Input Tokens Impacts LLM Performance](https://www.trychroma.com/research/context-rot) — 18 frontier models, distractor and length effects; accessed 2026-07-26
- [Letta — Memory Blocks: The Key to Agentic Context Management](https://www.letta.com/blog/memory-blocks/) — memory blocks, sleep-time compute; accessed 2026-07-26
- [LangChain — LangMem SDK launch](https://www.langchain.com/blog/langmem-sdk-launch) — semantic/episodic/procedural helpers over `BaseStore`; accessed 2026-07-26
- [Lost in the Middle: How Language Models Use Long Contexts](https://arxiv.org/abs/2307.03172) — positional degradation; accessed 2026-07-26

## Changelog
- 2026-07-26 — created
