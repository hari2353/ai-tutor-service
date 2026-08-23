# Lab 06: A RAG Pipeline From Scratch

**Track:** T06 RAG (Retrieval-Augmented Generation) · **Time:** 3.5h · **XP:** 50
**Modules:** `T06-chunking`, `T06-hybrid-search`

**You will build:** three chunking strategies (fixed, recursive, semantic-ish), BM25
from scratch with the real Okapi saturation formula, cosine-similarity dense
retrieval over fixed seeded vectors, and Reciprocal Rank Fusion -- all deterministic,
all offline.

**You will be able to answer:** *"Implement BM25 from scratch. Why does hybrid
search beat either retriever alone, and how would you prove it rather than just
assert it?"*

## Setup

```bash
cd labs/py/06-rag-pipeline
python -m venv .venv && . .venv/bin/activate     # or: uv venv && . .venv/bin/activate
pip install pytest numpy                          # only dependencies
```

## The spec

1. **`fixed_chunk(text, chunk_size, overlap=0)`** -- pack whole words into
   character-budget chunks. A word longer than `chunk_size` becomes its own
   (over-budget) chunk rather than being split. `overlap` repeats the trailing
   words of one chunk at the head of the next.
2. **`recursive_chunk(text, max_size, separators=None)`** -- try the coarsest
   separator first (`"\n\n"`), only descend to finer ones (`"\n"`, `". "`, `" "`)
   for pieces still too big. A paragraph that already fits stays intact --
   recursion is lazy, not eager. Falls back to `fixed_chunk` once separators run
   out, so it's word-safe by construction.
3. **`semantic_chunk(text, threshold=0.3, max_sentences=5)`** -- group consecutive
   sentences while cosine similarity to the running chunk centroid stays at or
   above `threshold`; start a new chunk when it drops below, or the chunk hits
   `max_sentences`. Sentence embeddings come from `seeded_embed`: a **deterministic
   bag-of-words hash embedding** (each word maps to a fixed pseudo-random unit
   vector seeded off its own MD5 hash; a sentence's embedding is the mean of its
   words' vectors). This is not a trained model -- it's "semantic-ish": genuinely
   driven by shared vocabulary, fully offline, fully reproducible.
4. **`BM25`** -- Okapi BM25 from scratch:
   `score = Σ_t idf(t) · f(t,d)·(k1+1) / (f(t,d) + k1·(1 - b + b·dl/avgdl))`,
   `idf(t) = ln((N - n(t) + 0.5)/(n(t) + 0.5) + 1)`. `.search()` returns docs
   sorted by score descending, ties broken by ascending doc id.
5. **`DenseRetriever`** -- cosine similarity search over a fixed dict of
   pre-computed doc vectors (no model call -- the vectors are given).
6. **`reciprocal_rank_fusion(rankings, k=60)`** -- fuse multiple ranked doc-id
   lists: `score(doc) = Σ 1/(k + rank)` over every list the doc appears in.

## Run the tests

```bash
pytest tests/ -v          # against starter/ → FAILS. Make them pass.
```

To check the reference: `pytest tests/ -v --solution`

The centerpiece test, `test_rrf_outperforms_either_retriever_alone`, uses a
10-document corpus with a fixed relevance judgment (`relevant = {2, 5}`) engineered
so doc 2 is a pure lexical match (BM25 finds it, dense doesn't) and doc 5 is a pure
semantic/paraphrase match sharing zero query terms (dense finds it, BM25 can't).
Neither retriever alone gets both into its top-4; RRF does. The recall numbers in
that test are not tunable after the fact -- they fall out of the fixed corpus and
fixed seeded vectors.

## Stretch goals

1. **Weighted score fusion** -- implement an alternative to RRF that normalizes and
   linearly combines the raw BM25 and cosine scores instead of using rank position.
   Show a case where it beats RRF and a case where it needs corpus-specific tuning
   RRF doesn't. *(Interview: "when does score fusion outperform rank fusion, and
   why is it riskier in production?")*
2. **Recall@k vs MRR** -- add a second, precision-sensitive metric (Mean Reciprocal
   Rank) alongside recall@k and show a scenario where the two disagree about which
   retriever is "better."
3. **Overlap-aware recursive chunking** -- extend `recursive_chunk` to accept an
   `overlap` parameter like `fixed_chunk` does, so retrieved chunks carry a bit of
   neighboring context.
4. **ColBERT-style late interaction (sketch only)** -- instead of one vector per
   doc, embed each token and score with MaxSim. You don't need to implement it --
   describe the storage blow-up (tokens, not docs) and when it's worth it.
