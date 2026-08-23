# Lab 04: Hybrid Search From Scratch

**Track:** T06 Retrieval · **Time:** 2h · **XP:** 50
**Modules:** `T06-hybrid-search` + `T06-vector-index-internals`

**You will build:** BM25, a pseudo-dense scorer over character 3-gram embeddings, reciprocal-rank fusion, and a deterministic hybrid search — the entire retrieval stack in ~100 lines of stdlib Python.

**You will be able to answer:** *"Why does hybrid retrieval beat either leg alone, and why fuse ranked lists instead of raw scores?"*

## Setup

```bash
cd labs/py/05-hybrid-search
python -m venv .venv && . .venv/bin/activate     # or: uv venv && . .venv/bin/activate
pip install pytest                                # only dependency
```

## The spec

The corpus everywhere is `docs: dict[str, str]` — doc id → text.

1. **`bm25(corpus_docs, k1=1.5, b=0.75)`** — returns a scorer with `.score(query, doc_id)` and `.rank(query)` (ids sorted by score desc, ties → id asc). Standard IDF: `ln((N − df + 0.5)/(df + 0.5) + 1)`. Terms are lowercase `\w+` runs.
2. **`dense_scorer(docs)`** — pseudo-embeddings: each text becomes a **character 3-gram TF vector** (lowercased, overlapping windows); scoring is cosine similarity between query vector and doc vector. Same `.score` / `.rank` interface. This is fake semantics — but it behaves like one: "engines" lights up for "engine" without sharing a token.
3. **`rrf(rankings, k=60)`** — reciprocal-rank fusion over a list of ranked id lists. Returns `{doc_id: fused_score}` where `score(d) = Σ_ranks 1/(k + rank_i(d))`, ranks starting at 1. Fusion happens on **ranks**, never raw scores — that's why it works across incomparable scorers.
4. **`hybrid_search(query, docs, top_n=10, k=60)`** — run both legs, RRF-fuse their rankings, return up to `top_n` `(doc_id, fused_score)` tuples sorted by fused score desc, with deterministic tie-break: higher bm25 first, then doc id asc. Empty/whitespace query → `[]`.

## Run the tests

```bash
pytest tests/ -v          # against starter/ → FAILS. Make them pass.
```

To check the reference: `pytest tests/ -v --solution`

## Stretch goals

1. **Real embeddings** — swap the 3-gram leg for hashed bag-of-words with IDF weighting. Where does the analogy to trained encoders break?
2. **Weighted fusion** — `alpha * bm25_rank + (1−alpha) * dense_rank` vs RRF. Plot recall@k over alpha on a toy set. *(Interview: "why do production systems mostly ship RRF anyway?")*
3. **Index internals** — invert the BM25 index ( postings lists ) and compare memory/scoring cost vs scanning every doc. When does an ANN index (HNSW/IVF) actually pay off?
4. **Async port** — fuse legs concurrently with `asyncio.gather`; note where the GIL makes this theatre.
