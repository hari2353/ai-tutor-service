# Lab 15: Semantic Caching — Exact, Prefix, and Similarity Layers From Scratch

**Track:** T06 RAG (Retrieval-Augmented Generation) · **Time:** 2h · **XP:** 50
**Module:** `T06-semantic-caching`

**You will build:** a three-layer LLM response cache — byte-exact hashing with TTL, whitespace-normalized longest-prefix reuse with a continuation marker, and char-3gram Jaccard semantic matching with a tunable threshold — over one backing entry store, with stats you can actually do math on.

**You will be able to answer:** *"Why does a production LLM stack need three cache layers instead of one good embedding cache — and where does each layer's correctness risk come from?"*

## Setup

```bash
cd labs/py/15-semantic-cache
python -m venv .venv && . .venv/bin/activate     # or: uv venv && . .venv/bin/activate
pip install pytest                                # only dependency
```

## The spec

All time flows through an injectable `Clock` (`SystemClock` / `FakeClock(t)` with `.advance(dt)`). Everything is model-scoped: a lookup may only ever see entries stored under the same `model` — that isolation rule applies to *all three layers*, not just the exact hash.

1. **Text ops** — `normalize(text)`: lowercase, drop punctuation, collapse whitespace runs (prefix + semantic layers ONLY). `char_3grams(text)`: trigram set over the normalized text (short strings fall back to `{normalized}`; empty → empty set). `jaccard(a, b)`: `|a∩b| / |a∪b|`, two empty sets → `0.0`. `common_prefix_len(a, b)`.
2. **`exact_key(model, params, prompt)`** — sha256 over the full request JSON (`sort_keys=True` so param order never matters); the raw prompt goes in untouched.
3. **`SemanticCache(backend_fn, clock=..., ttl=300, prefix_min_chars=20, threshold=0.6, capacity=128)`** — `.ask(prompt, model=..., params=...)` checks layers in order:
   - **Exact**: hash hit on raw bytes → serve verbatim. Any changed character, case, space, or param value misses this layer by construction.
   - **Prefix**: longest common *normalized* prefix ≥ `prefix_min_chars` → serve the cached answer **with `PREFIX_CONTINUATION_MARKER` appended**, plus `.prefix_chars` recording how much was shared. (`None` disables.)
   - **Semantic**: nearest neighbour among same-model entries by trigram Jaccard; score ≥ `threshold` → serve it, record `.similarity`. (`None` disables.) This is the only layer that can be wrong on a hit — the threshold is the knob that decides how often.
4. **Miss path** — call `backend_fn(prompt)` exactly once, insert ONE entry carrying all three views (raw / normalized / trigrams), evicting oldest-inserted entries beyond `capacity`. One fill populates every layer; there is no per-layer write logic.
5. **TTL & eviction** — expiry is lazy (`now - ts >= ttl`) and purges only expired entries without counting as eviction; capacity eviction counts in `stats.evictions`.
6. **Stats** — `stats.as_dict()` → `{exact_hits, prefix_hits, semantic_hits, misses, evictions}`; `hit_rate()` = hits / (hits + misses), `0.0` before any ask. `invalidate(model)` drops only that model's entries.

## Run the tests

```bash
pytest tests/ -v          # against starter/ → FAILS. Make them pass.
```

To check the reference: `pytest tests/ -v --solution`

## Stretch goals

1. **Embedding swap** — keep the interface, replace trigram Jaccard with real embeddings behind the same `similarity(query, entry)` seam. Measure hit-rate change on a fixed paraphrase set. *(Interview: "what did the cheap proxy miss?")*
2. **Positive hit rate** — thread an optional verifier callable through `ask()` and report `stats.false_hits`; reproduce the curriculum's annual-vs-monthly false hit at 0.9 similarity and show the verifier catching it.
3. **Adaptive threshold** — per-entry vCache-style threshold nudged by observed outcomes instead of one global number.
4. **Async port** — non-blocking lookups against an asyncio backend; note which parts get simpler and which race now.
