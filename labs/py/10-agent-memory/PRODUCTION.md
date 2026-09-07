# Production notes — agent memory

## What you'd actually use

| Your piece | Real thing | What it adds over yours |
|---|---|---|
| WorkingMemory eviction | every context manager: llm-context-engine, LangChain trimmers, Anthropic prompt caching + context editing | real tokenizers (tiktoken), role-aware trimming, *cached prefixes* so eviction doesn't re-bill |
| EpisodicMemory (bag-of-words) | vector DBs: pgvector, Qdrant, Chroma; Letta's archival memory | embeddings + ANN indexes, metadata filters, hybrid BM25+vector, rerankers |
| SemanticMemory (KV + contradictions) | Letta core memory blocks; Zep/Graphiti knowledge graphs; mem0 fact extraction+consolidation | entity-resolution, temporal validity intervals (Zep's "valid_at"), automatic fact merging |
| ProceduralMemory | Letta's `core_memory`+skills, Voyager's skill library, DSPy programs/few-shot caches | *learned* instructions (optimizer-written), versioned skills, retrieval by embedding not regex |
| The composed whole | Letta (formerly MemGPT), mem0, Zep | memory as an operating system: page-in/out between context and storage, background consolidation, multi-user scoping |

The systems to name in interviews: **Letta/MemGPT** (context-as-RAM, archival-as-disk, the agent pages memories in by emitting special tool calls), **mem0** (LLM extracts facts from conversations, consolidates: ADD/UPDATE/DELETE/NOOP decisions against existing store), **Zep/Graphiti** (temporal knowledge graph — facts have validity intervals, so "lives in Oslo" *ends* when "lives in Lisbon" begins, no contradiction, just time).

## What the real ones add over yours

- **Semantic retrieval, not lexicons.** Your Jaccard bag-of-words misses "cat" vs "kitten". Production embeds both sides and does ANN search — then hybridises with keyword/BM25 and reranks. Your version is still the right *architecture*, just with the cheapest possible similarity. The failure mode interviewers probe: paraphrase invisibility.
- **Contradiction resolution with temporal semantics.** You keep both versions with dates — honest, but the agent must reason about it. Zep models facts as time-scoped edges (`valid_at` / `invalid_at`): the newest fact is *currently* true, the old one isn't false, just expired. mem0 instead runs UPDATE/DELETE decisions — cheaper, lossier.
- **Consolidation passes.** mem0's core loop: after each turn, an LLM diffs the conversation against memory ("new fact? update? contradiction? nothing?"). You don't auto-promote episodic → semantic; production does, as a background job. That's also where token cost concentrates — why "memory ops" get their own cheap model.
- **Multi-user, multi-session scoping.** Every store above is keyed by (user_id, agent_id, session). Your memories are single-tenant; cross-session leakage is the classic production bug.
- **Provenance and privacy.** Your `source` field is the right instinct. Production adds: per-fact TTL/retention (GDPR delete), scopes ("this fact is OK in work threads only"), and audit trails. Deletion must propagate through indexes, backups, and embedding stores — the part everyone forgets.

## What breaks at scale

| Symptom | Cause | Fix |
|---|---|---|
| Agent "forgets" mid-task facts | eviction ate the current task's context | pin working blocks (task/todo pinned, history evicted) |
| Retrieval surfaces embarrassing old episodes | no decay, no session filter | recency weighting, session scoping, minimum similarity floor |
| Facts contradict wildly | last-write-wins or naive LLM updates | temporal model or explicit consolidation pass (mem0) |
| Memory calls cost more than LLM calls | every turn = extract + consolidate + embed | batch consolidation, cheap model for ops, cache prefixes |
| Vector index at 100M memories | flat search | ANN (HNSW), sharding, metadata prefilter |
| Same skill always wins | first-registered match, no stats used | score by success_rate (your prune is the start) |
| Tests flaky | wall-clock in timestamps | inject the clock — that's requirement #1 here too |
| Prompt explodes with "relevant" memories | k too high, no budget | memory has a token budget like WorkingMemory; rerank and cap |

## The 3 questions an interviewer asks after you describe this

1. *"Why not just put everything in the context window?"* — cost (quadratic attention, per-token billing), latency, and the model's *middle* attention weakness — plus a 10M-token window still can't hold a year of user history. Memory is a *retrieval* problem, not a *size* problem.
2. *"Where do embeddings actually matter in your design?"* — episodic + procedural retrieval (paraphrase matching). Working memory is budget management; semantic memory is curation/consistency — embeddings don't fix contradictions, the consolidation policy does. Knowing which layer needs which mechanism is the actual answer.
3. *"Your semantic memory keeps both sides of a contradiction. Won't the agent use the stale one?"* — lookup returns latest (recency), history returns both (provenance); the agent prompt gets the fact *with its date and source*, so "user said in March they were vegan, in June they weren't" is a feature. The failure mode is silently collapsing to last-write-wins without telling anyone *when*.
