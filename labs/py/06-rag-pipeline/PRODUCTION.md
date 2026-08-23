# Production notes -- the RAG pipeline

## What you'd actually use

| Concern | Roll-your-own (this lab) | Production reach-for |
|---|---|---|
| Chunking | fixed/recursive/semantic-ish, in-process | LangChain/LlamaIndex `RecursiveCharacterTextSplitter` as the default; contextual retrieval (Anthropic, Sept 2024) or late chunking for the decontextualization problem |
| Sentence embeddings for chunking | hashed bag-of-words (deterministic, offline) | a real sentence embedding model (small, fast one -- this is a cheap per-chunk call, not the retrieval-time one) |
| BM25 | hand-rolled, in-memory dict | Elasticsearch/OpenSearch, or `rank-bm25`/`bm25s` in Python -- same math, but with proper inverted indexes so it scales past what fits in a dict |
| Dense retrieval | linear scan over a Python dict | a real ANN index (HNSW via FAISS/pgvector/Qdrant) -- exact cosine over millions of vectors is too slow; ANN trades a small recall loss for sub-linear search |
| Query embedding | given as a fixed test fixture | a real embedding model call (OpenAI/Cohere/local), cached, batched |
| Fusion | RRF, computed once per query | RRF or weighted fusion, same math, but the reranker (a cross-encoder) usually runs on top of the fused top-k before anything reaches the LLM |
| Corpus | 10 hardcoded strings | a document store with versioning, so re-indexing after a corpus update doesn't require rebuilding everything from scratch |

## What the real ones add over yours

- **A real embedding model, not a hash.** `seeded_embed` is deterministic and
  testable, which is exactly why it's not a real embedding: it only "understands"
  shared vocabulary, not paraphrase or synonymy. A real model (even a small one)
  is what actually makes dense retrieval find "how do I undo a git commit" when the
  doc says "reverting a change" with zero shared words.
- **An ANN index, not a linear scan.** `DenseRetriever.search` here is O(N) per
  query -- fine for 10 docs, wrong for 10 million. HNSW gets you O(log N)-ish at
  the cost of being approximate: you trade a small, tunable recall loss for a
  massive speedup, and you have to *measure* the recall loss, not assume it's
  negligible.
- **An inverted index, not `.count()` on a token list.** This lab's `BM25.score`
  scans every doc's token list per query term. Production BM25 (Elasticsearch,
  Lucene) maintains an inverted index (term → postings list of doc ids + term
  frequencies) so scoring only touches docs that actually contain the query terms.
- **A reranker after fusion, not fusion as the final step.** RRF and weighted
  fusion are cheap and fast but rank-only; a cross-encoder reranker looks at the
  full (query, doc) pair together and is far more accurate at the top of the list,
  at the cost of being too slow to run over the whole corpus -- so it only reranks
  the fused top-k (typically 20-100 candidates) before the top 3-10 go to the LLM.
- **Chunking that's corpus- and query-aware.** Chunk size is not a universal
  constant. Production teams pick it empirically against a recall@k eval set built
  from their own corpus and query distribution -- the "right" chunk size for legal
  contracts and the "right" chunk size for chat transcripts are not the same
  number, and neither is derived from a blog post default.

## What breaks at scale

| Symptom | Cause | Fix |
|---|---|---|
| Retrieval quality quietly degrades after a corpus update | No recall@k eval set, no regression check on re-index | Keep a small, hand-labeled (query, relevant-doc) set like the RRF test fixture in this lab, run it on every re-index |
| Dense retrieval search gets slower every month | Linear scan (or a naive index) growing with corpus size | Move to ANN (HNSW/IVF) before it becomes the bottleneck, not after |
| Hybrid search returns garbage for exact-ID queries ("error code E4021") | Dense retrieval blurs past exact identifiers; BM25 was dropped or under-weighted | Never ship dense-only retrieval for a corpus with structured/exact-match content; BM25 is not legacy, it's complementary |
| RRF's `k` constant needs re-tuning per corpus | `k=60` is a convention, not a law -- it controls how much weight top ranks get relative to the rest of the list | Treat `k` as a hyperparameter, sweep it against the recall@k eval set like any other |
| A chunk cuts a table row or code block in half | Naive fixed-size chunking ignoring document structure | Structure-aware (recursive/markdown-aware) splitting, or don't chunk structured content the same way as prose |
| "Who is 'the company'?" -- a chunk loses its referent | Chunking destroys context that only existed in a sibling chunk | Contextual retrieval (prepend an LLM-written one-line context to each chunk before embedding) or late chunking (embed with full-document context, chunk after) |

## Cost & latency

BM25 over an inverted index is single-digit milliseconds even at millions of docs
-- it's essentially free compared to the LLM call downstream. Dense retrieval's
cost is dominated by the embedding call for the *query* (one call per request,
cents or less) and the ANN search itself (milliseconds if properly indexed).
Reranking is the expensive step: a cross-encoder over even 50 candidates is
50 forward passes, tens to low-hundreds of milliseconds on GPU. The chunking
decision is a one-time (well, one-time-per-reindex) cost, but it is the single
highest-leverage decision in the whole pipeline because every downstream metric
is bounded by whether the chunk boundary preserved the answer -- get retrieval and
fusion perfect over badly-chunked text and you still fail.

## The 3 questions an interviewer asks after you describe this

1. *"Your RRF test shows fusion beating both retrievers on one engineered query.
   How would you know it generalizes?"* -- one query proves the mechanism works;
   production needs a relevance-judged eval set across representative query types
   (exact-match, paraphrase, multi-hop) with recall@k/NDCG tracked over time, not a
   single anecdote.
2. *"Why not just always use dense retrieval -- embeddings are supposed to capture
   meaning?"* -- embeddings blur past exact identifiers, rare terms, and negation
   (they cluster "I love this product" and "I don't love this product" closer than
   intuition suggests); BM25 is a hard floor for lexical precision that no
   single-vector embedding reliably provides.
3. *"Your BM25 doc frequency (`df`) never gets recomputed. What happens when the
   corpus grows by 10x?"* -- `idf` values (and `avgdl`) are corpus statistics; a
   growing corpus without periodic recomputation drifts, and stale idf values
   quietly bias scoring toward whatever term rarity looked like at index-build
   time, not now.
