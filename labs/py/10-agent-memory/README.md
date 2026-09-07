# Lab 10: The Four Memory Types

**Track:** T07 Agentic AI · **Time:** 2.5h · **XP:** 50
**Module:** `T07-agent-memory`

**You will build:** the four memories an agent carries — `WorkingMemory` (bounded message deque with token-estimate eviction and pinned system prompts), `EpisodicMemory` (append episodes, top-k retrieval by bag-of-words overlap), `SemanticMemory` (key-value facts with source/confidence and *contradictions kept with dates*), `ProceduralMemory` (skill library with trigger patterns, match, success stats, pruning) — all deterministic via an injectable clock.

**You will be able to answer:** *"Agents say they have 'memory'. Name the four types, what goes in each, and what breaks when you only have the context window."*

## Setup

```bash
cd labs/py/10-agent-memory
python -m venv .venv && . .venv/bin/activate     # or: uv venv && . .venv/bin/activate
pip install pytest                                # only dependency
```

## The spec

1. **`Clock`** — `SystemClock` / `FakeClock(t=0)` with `advance(dt)`; every timestamp in every memory comes from it.
2. **`WorkingMemory(max_tokens)`** — message deque `(role, content)`; `_estimate_tokens` ≈ chars/4 (min 1). `add()` evicts oldest **non-pinned** messages until under budget; pinned (`add(..., pinned=True)`) never evict; all-pinned-and-over-budget keeps everything. `messages()` returns clean `(role, content)` pairs; `tokens_used()` sums estimates; evictions recorded as `Eviction(role, content, tokens)`.
3. **`EpisodicMemory`** — `record(content)` stamps clock time; `retrieve(query, k)` ranks by `overlap_similarity` (Jaccard over lowercase word bags), zero-overlap episodes excluded, ties broken by earlier timestamp, sets `.score` on returns. Tokenizer: `[a-z0-9']` runs.
4. **`SemanticMemory`** — `insert(key, value, source, confidence)`; `lookup` = latest; `history` = all versions in order; `contradictions()` = keys with >1 distinct value. **A contradicting write never overwrites** — both facts stay, with dates.
5. **`ProceduralMemory`** — `register(name, trigger_regex, instructions)` (case-insensitive); `match(query)` = first registered hit; `match_all`; `record_success`/`record_failure` bump stats and stamp `last_used_at`; `prune(min_success_rate, min_uses)` removes proven under-performers and returns their names; young skills (`uses < min_uses`) are protected.
6. **`AgentMemory`** — one clock wired through all four.

## Run the tests

```bash
pytest tests/ -q          # against starter/ → FAILS. Make them pass.
```

To check the reference: `pytest tests/ -q --solution`

## Stretch goals

1. **Semantic decay** — facts' confidence decays with clock time; lookup filters below 0.3. What policy re-surfaces a decayed fact? (A later corroborating insert.)
2. **Recency-weighted retrieval** — `similarity * 1/(1+age)` on the injectable clock. How does the weighting change what the agent "remembers"?
3. **Real embeddings** — swap bag-of-words for numpy cosine similarity over hashed n-grams (no network). What fails to improve? (Word order, synonyms need trained vectors.)
4. **Forgetting policy** — episodic memory bounded by count+age with a promotion rule to semantic (facts seen ≥ N times). This is mem0's actual architecture.
