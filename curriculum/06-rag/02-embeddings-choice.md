# Embedding Models: Dimensions, Matryoshka, Multilingual, Cost

> **Track:** T06 RAG (Retrieval-Augmented Generation) · **Time:** 1.5h · **Prereqs:** 01-chunking · **Updated:** 2026-07-27
> **Module id:** `T06-embeddings-choice` · **Tags:** ingest

## The 30-second version

Every embedding decision is really three decisions bundled together: which model's semantic quality you're buying, how many dimensions you're paying to store and search, and whose infrastructure computes the vector. Matryoshka Representation Learning (Kusupati et al., 2022) changed the second decision entirely — modern embedding models (OpenAI text-embedding-3-*, Cohere embed-v4, Voyage-3.5, Gemini Embedding, Nomic v1.5) train nested representations so you can truncate a 3072-dim vector down to 256 dims and keep most of the retrieval quality, instead of needing a smaller model. On raw MTEB numbers Cohere embed-v4 (65.2), OpenAI text-embedding-3-large (64.6), and BGE-M3 (63.0) all cluster close together, which means the model choice is rarely the lever that matters most — index size, latency budget, and whether you need multilingual or multimodal support usually decide it before quality does. Open-weight models (BGE-M3, Nomic, E5) remove the per-token API cost entirely at the price of owning the GPU serving stack; API models (OpenAI at $0.02–0.13/1M tokens, Cohere at $0.12/1M) remove the ops burden at the price of a per-query network hop and a vendor dependency for the one artifact — the embedding space — that every downstream index is keyed on. Re-embedding a corpus after switching models is not a config change; it's a full reindex, so the real cost of an embedding choice is the migration cost of the *next* one.

## Why this gets asked

The interviewer has watched a team pick an embedding model once, in a demo, and never revisit it — then discover eighteen months later that upgrading to a better model means re-embedding 40M chunks, re-running the ANN index build, and running a shadow evaluation, all while serving traffic on the old vectors. They want to know whether you think of embedding choice as a one-time model-quality decision or as a long-lived infrastructure commitment with a real migration cost, and whether you know the specific levers (Matryoshka truncation, quantization, instruction prefixes) that let you tune cost without a full model swap.

---

## Lineage: past → present → future

**What came before.** Sparse, count-based representations — TF-IDF and BM25 — were the default retrieval mechanism for decades because they're cheap, interpretable, and need no training, but they only match on shared tokens: a query for "car" scores zero relevance against a document that only says "automobile." Static word embeddings (word2vec, GloVe, 2013–2014) fixed part of this by giving every word a fixed dense vector trained on co-occurrence, capturing analogical structure ("king - man + woman ≈ queen"), but a word had exactly one vector regardless of context — "bank" the riverbank and "bank" the financial institution collapsed to the same point. Contextual embeddings from transformer encoders (BERT, 2018) fixed *that*, giving each token a vector conditioned on its surrounding context, but raw BERT token embeddings are poor at whole-sentence similarity out of the box — pooling raw BERT outputs for retrieval underperforms even simple averaged word vectors on semantic textual similarity benchmarks, because BERT was pretrained for masked-token prediction, not for making semantically similar sentences land close together in vector space. Sentence-BERT (Reimers & Gurevych, 2019) is the paper that actually fixed the retrieval use case: fine-tune a BERT-style encoder with a contrastive or triplet loss so that semantically similar sentences are pulled together and dissimilar ones pushed apart, producing a single pooled vector suited to cosine/dot-product search. Every modern embedding model — OpenAI's, Cohere's, BGE, E5, Voyage — is a direct descendant of this bi-encoder-plus-contrastive-loss recipe, trained on vastly more data and with far larger backbones.

**Where it stands now.** The bi-encoder is the unchallenged default for first-stage retrieval because it lets you embed the corpus once, offline, and only embed the query at request time — a cross-encoder that jointly scores query and document can't do this and is reserved for reranking a small candidate set (see `05-reranking.md`). On MTEB (Massive Text Embedding Benchmark), commercial and open models now cluster tightly: Cohere embed-v4 leads at roughly 65.2, OpenAI text-embedding-3-large at 64.6, and the open-weight BGE-M3 at 63.0 — a two-point spread that rarely decides a production outcome the way dimensionality, latency, or multilingual coverage does. The live disagreement is less "which model" and more "open weights vs. API": self-hosting BGE-M3 or a similar open model removes per-token cost and vendor lock-in on the one artifact everything downstream depends on, at the cost of owning GPU serving, batching, and version-pinning; API models remove that ops burden but tie your entire index to a provider's uptime and pricing. Matryoshka Representation Learning is the other genuine shift: nearly every current-generation model (OpenAI text-embedding-3-*, Cohere embed-v4, Voyage-3.5, Gemini Embedding 2, Nomic v1.5, Jina v5, Microsoft Harrier) now trains so that a prefix of the full-dimension vector — the first 256 or 512 dims of a 3072-dim output — is itself a valid, only-mildly-degraded embedding, which means dimensionality became a runtime knob instead of a model-selection decision.

**Where it's heading.** Instruction-tuned and task-conditioned embeddings — where the same model produces a different vector for the same text depending on a natural-language instruction prefix ("represent this for retrieval" vs. "represent this for clustering") — are shipping now (E5-instruct, BGE's instruction variants, Voyage's input-type parameter) and moving toward becoming the default rather than an option, moderate-to-high confidence, because a single well-instructed model can replace several task-specific ones. Unified multimodal embedding spaces (text, image, and increasingly audio in one shared space, as Cohere embed-v4 and Voyage multimodal-3 already do) are the clear direction of travel for any RAG system ingesting PDFs with figures or slide decks — high confidence, already deployed. More speculative: embeddings that adapt their own dimensionality or precision per-query based on a latency budget signal, rather than a single fixed truncation chosen at index time, and embedding models trained jointly with the downstream retriever's ANN index structure rather than as an independent artifact — both exist only as research directions as of mid-2026, not shipped patterns.

---

## Mental model

An embedding model is a lossy compression function from "everything about this text's meaning" down to a fixed-size vector. Two knobs control the compression:

```
                     more dimensions
                     ─────────────────►
              256          768          1536          3072
   quality    ok           good         very good     best
   storage    1x           3x           6x            12x   (relative to 256d @ fp32)
   ANN speed  fastest      fast         slower        slowest

Matryoshka training makes the LEFT side of this axis a truncation
of the RIGHT side of the SAME vector, not a different model:

   [ d0 d1 d2 ... d255 | d256 ... d767 | d768 ... d1535 | ... ]
     └── 256-dim vec ──┘
     └──────── 768-dim vec ─────────┘
     └────────────────── 1536-dim vec ──────────────────┘

Truncate anywhere along the prefix and re-normalize -> a valid,
just slightly lower-quality embedding. No retraining, no new
inference call -- you already have the full vector, you're
choosing how much of it to keep in the index.
```

Instruction prefixes are the second knob, orthogonal to dimension: the same backbone, given a different natural-language task description ("query:" vs. "passage:", or a longer instruction like "represent this document for retrieval given a search query"), rotates the output vector into a subspace better suited to that task without changing dimensionality at all.

---

## How it actually works

### Bi-encoder architecture and pooling

A bi-encoder passes text through a transformer encoder to get per-token contextual embeddings, then pools them into one fixed-size vector — mean pooling over all tokens (average, masking out padding) is the most common choice and what Sentence-BERT popularized; some models instead use the `[CLS]` token's final-layer representation, or a learned attention-weighted pool. Mean pooling generally outperforms raw `[CLS]` pooling for retrieval because it aggregates signal from the whole sequence rather than relying on a token that BERT-style pretraining never specifically optimized for sentence-level meaning.

Training uses a contrastive objective — InfoNCE or a triplet loss — over (query, positive passage, hard negatives) triples: pull the query and its true positive together in vector space, push it away from in-batch negatives and mined hard negatives (passages that are lexically similar but semantically wrong, which is what actually teaches the model to disambiguate rather than just cluster by topic). The quality ceiling of an embedding model is largely a function of how good its hard-negative mining was during training, not raw parameter count — this is why domain-specific fine-tunes (legal, code, biomedical) beat larger general-purpose models on their own domain despite being smaller.

### Matryoshka Representation Learning — the mechanism

Standard contrastive training only supervises the full-dimension output vector. MRL (Kusupati et al., NeurIPS 2022) adds the same contrastive loss simultaneously at multiple nested prefix lengths of the same vector during training — for example computing loss at 64, 128, 256, 512, 768, 1024, 1536, and the full dimension all at once, summed or averaged. This forces the model to front-load the most discriminative information into the earliest dimensions, so that truncating the vector to any of those prefix lengths at inference time still yields a usable embedding, degrading gracefully rather than catastrophically.

```python
# untested sketch — Matryoshka truncation at inference time
import numpy as np

def truncate_matryoshka(embedding: np.ndarray, target_dim: int) -> np.ndarray:
    truncated = embedding[:target_dim]
    # re-normalize: cosine similarity assumes unit vectors, and a raw prefix
    # of a normalized vector is no longer unit-length
    norm = np.linalg.norm(truncated)
    return truncated / norm if norm > 0 else truncated
```

Concretely, with OpenAI's `text-embedding-3-large` (3072-dim, $0.13/1M tokens) you can request `dimensions=256` directly in the API call and OpenAI truncates and renormalizes server-side — this is not a hack, it's the trained behavior. Cohere embed-v4 exposes the same idea via `output_dimension` (256/512/1024/1536). The practical upshot: you almost never need to pick a smaller *model* purely to save storage or latency — pick the best model and truncate its dimension until your recall@k eval says you've given up too much.

### Instruction / task prefixes

Several current models (E5-instruct, BGE's instruction-tuned variants, Voyage's `input_type` parameter distinguishing `query` vs. `document`) require or strongly benefit from a task-specific prefix prepended to the raw text before embedding. Skipping this is a common, silent quality bug: embedding a query with no `query:` prefix against passages embedded with a `passage:` prefix on an instruction-trained model can measurably underperform doing it consistently either way, because the model learned two different subspace rotations for the two roles. Always check the model card for the required prefix convention before assuming raw text works.

### Cost math — know this cold

Embedding cost has two components: the one-time ingestion cost (embed every chunk once) and the per-query cost (embed every query at request time). For a corpus of 10M chunks averaging 250 tokens each:

```
ingestion tokens  = 10,000,000 * 250 = 2.5B tokens
OpenAI 3-small ($0.02/1M)   -> $50 one-time
OpenAI 3-large ($0.13/1M)   -> $325 one-time
Cohere embed-v4 ($0.12/1M)  -> $300 one-time
Self-hosted BGE-M3          -> $0 API cost, but GPU-hours to embed 2.5B tokens
                                (throughput-dependent; budget for a batch job,
                                 not a blocking pipeline step)
```

Query-time cost is comparatively trivial (a handful of tokens per query) but the *latency* of that embedding call is not: a network round trip to an API embedding endpoint typically adds 30-80ms to time-to-first-retrieved-chunk, which is why latency-sensitive services often self-host a small, fast embedding model even when they use an API model or a larger self-hosted model for reasoning.

Storage cost is where dimension actually bites. A 10M-chunk corpus at 1536 dimensions in float32 is `10M * 1536 * 4 bytes = 61.4 GB` of raw vector data before any index overhead (see `03-vector-index-internals.md` for the full HNSW memory formula); truncating to 512 dimensions via Matryoshka drops that to 20.5 GB — a 3x reduction with, on most current MRL-trained models, single-digit-percent recall loss on the eval, not a proportional 3x quality loss.

### Quantization stacks with Matryoshka, not instead of it

Scalar quantization (float32 → int8) and binary quantization (1 bit/dimension) are a second, independent compression axis — Matryoshka reduces *how many* dimensions you store; quantization reduces *how many bits per dimension* you store. Combining both (e.g., 512-dim Matryoshka truncation + int8 scalar quantization) is common in production and can bring the 61.4 GB example above down to roughly 5 GB, at a further, larger recall cost that must be validated on your own eval set — quantization's accuracy hit is much less uniform across models than Matryoshka's trained-in graceful degradation.

---

## Build it from scratch

A minimal bi-encoder retrieval loop using a small open-weight model, showing where the prefix and dimension decisions actually happen:

```python
# untested sketch — minimal bi-encoder embed + cosine retrieval
from sentence_transformers import SentenceTransformer
import numpy as np

model = SentenceTransformer("BAAI/bge-small-en-v1.5")  # 384-dim, instruction-aware

def embed_passages(passages: list[str]) -> np.ndarray:
    # BGE convention: no prefix needed for passages
    vecs = model.encode(passages, normalize_embeddings=True)
    return vecs

def embed_query(query: str) -> np.ndarray:
    # BGE convention: queries need this instruction prefix for retrieval tasks
    prefixed = f"Represent this sentence for searching relevant passages: {query}"
    return model.encode([prefixed], normalize_embeddings=True)[0]

def top_k(query_vec: np.ndarray, passage_vecs: np.ndarray, k: int = 5) -> list[int]:
    # normalized vectors -> cosine similarity is just the dot product
    scores = passage_vecs @ query_vec
    return list(np.argsort(-scores)[:k])
```

For a from-zero Matryoshka evaluation harness comparing recall@10 across truncation levels on your own corpus, see `labs/python/02-embeddings-choice/`.

---

## How it's done in production

**OpenAI** (`text-embedding-3-small`/`-large`) — simplest to operate, Matryoshka via `dimensions=` param, no self-hosting. **Cohere** (`embed-v4`) — multimodal (text+image), strong multilingual (MIRACL benchmark leader), `output_dimension` param, 128K context. **Voyage AI** (`voyage-3.5` family) — commonly reported as the strongest for code and technical documentation retrieval, Matryoshka 2048→256, `input_type` distinguishes query/document. **BGE-M3** (BAAI, open weights) — 568M params, 100+ languages, unifies dense + sparse (learned lexical) + multi-vector (ColBERT-style) retrieval in one model, 8192-token context; the default open-weight choice when you need to self-host. **Nomic Embed v1.5** — open weights, Matryoshka-trained, popular for fully local/on-prem deployments. **Gemini Embedding** — competitive MTEB, Matryoshka-trained, tightly integrated if already on Vertex AI.

| Symptom | Cause | Fix |
|---|---|---|
| Recall drops sharply after "upgrading" embedding model | Old and new vectors are not comparable — cosine similarity between a text-embedding-3 vector and a BGE-M3 vector is meaningless; this requires a full reindex, not a rolling upgrade | Treat any embedding model change as a migration project: re-embed the full corpus, build a new index, shadow-evaluate against the old one, then cut over |
| Query results look subtly worse after switching to an instruction-tuned model | Missing or inconsistent query/passage prefix convention | Check the model card for required prefixes; apply consistently at both ingestion and query time |
| Index storage 2-3x larger than budgeted | Storing full-dimension float32 vectors when Matryoshka truncation or quantization was assumed in the sizing estimate | Verify actual bytes/vector against the plan; apply `dimensions=` truncation or scalar/binary quantization and re-validate recall |
| p99 query latency has an unexplained 30-80ms floor | Synchronous network call to an API embedding endpoint for every query | Cache frequent queries' embeddings, batch where possible, or self-host a small fast model for the query-embedding hop specifically |
| Multilingual queries return poor results despite a "multilingual" model card claim | Not all "multilingual" models are equally strong across all claimed languages — coverage is uneven, often English/Chinese/Spanish-heavy | Benchmark on your actual target languages, not the model's aggregate MTEB score (see `12-multilingual.md`) |
| Cross-lingual or cross-model similarity scores look randomly distributed | Comparing vectors from two different embedding models, or assuming a model trained for monolingual retrieval generalizes cross-lingually | Confirm the model was specifically trained/evaluated on cross-lingual retrieval (e.g., MIRACL) before assuming cross-lingual search works |

---

## Tradeoffs & when NOT to use it

- **Don't pick the highest-MTEB model reflexively.** The two-point gap between top commercial and open models rarely survives contact with your actual corpus and query distribution; run your own recall@k eval before committing, because MTEB is an aggregate over dozens of unrelated tasks and your domain may sit far from the average.
- **Don't self-host purely to save API cost if you don't already operate GPU inference.** The ops burden of batching, autoscaling, and version-pinning an embedding model is a real, ongoing cost that frequently exceeds the API bill it replaces, especially below tens of millions of embedding calls per month.
- **Don't truncate dimensions below what your eval validates**, even though Matryoshka degrades gracefully — "graceful" is relative to the full vector, not an absolute guarantee that 128 dims is fine for your domain; some domains (legal, technical) need more of the vector's capacity than casual FAQ retrieval does.
- **Don't assume a single embedding model serves both retrieval and clustering/classification well** without checking whether it's instruction-tuned for the specific task; a model optimized purely for retrieval contrastive loss can underperform on tasks it wasn't trained for.
- **Don't switch embedding models without budgeting the full reindex** — this is the single most underestimated cost in this decision; an embedding model choice is a long-lived infrastructure commitment, not a config value.

---

## Interview questions

### Q1 — Why can't you compare a cosine similarity score between two different embedding models?
**Testing:** basic understanding that embedding spaces are model-specific, not universal.
**Answer:** Each model learns its own vector space during training; there's no guarantee (and generally no truth) that two different models' coordinate systems align, so a vector from model A and a vector from model B occupy unrelated spaces even if both are unit-normalized. Comparing them numerically will produce a number, but it's meaningless.
**Follow-up trap:** *"What about two versions of the same model family, like text-embedding-3-small and -large?"* — still not comparable; different training runs, different dimensionality, no guaranteed alignment unless the vendor explicitly states otherwise.

### Q2 — What is Matryoshka Representation Learning and why does it matter operationally?
**Answer:** MRL trains the model with a contrastive loss applied simultaneously at multiple nested prefix lengths of the same output vector, so any prefix (256, 512, 768... dims) of the full vector is itself a usable, gracefully-degraded embedding. Operationally this turns dimensionality from a model-selection decision into a runtime truncation knob — you can shrink storage and search latency without retraining or picking a smaller model.
**Follow-up trap:** *"Does truncating always work regardless of the model?"* — no, only on models specifically trained with an MRL-style multi-length objective; truncating an arbitrary non-Matryoshka embedding's dimensions is not supported and degrades unpredictably, sometimes catastrophically.

### Q3 — Walk through the cost of embedding a 10M-chunk, 250-tokens-average corpus with OpenAI text-embedding-3-large.
**Answer:** 10M × 250 = 2.5B tokens, at $0.13/1M tokens = $325 one-time ingestion cost. Storage at full 3072 dimensions in float32 is 10M × 3072 × 4 bytes ≈ 123 GB before index overhead; truncating to 512 dims via the `dimensions=` parameter drops that to roughly 20.5 GB.
**Follow-up trap:** *"Is that the full cost of switching to this model?"* — no, this is only ingestion; the recurring cost is per-query embedding calls plus network latency, and if this replaces an existing model, add the cost of re-embedding the entire existing corpus and rebuilding the ANN index.

### Q4 — What's the difference between mean pooling and CLS-token pooling, and why does it matter for retrieval quality?
**Answer:** Mean pooling averages all non-padding token embeddings from the final layer into one vector; CLS pooling uses only the special classification token's final representation. Mean pooling generally performs better for retrieval because it aggregates signal across the whole sequence, while raw CLS embeddings from a model not specifically fine-tuned for sentence-level tasks (plain BERT, for instance) were never optimized to summarize the whole input.
**Follow-up trap:** *"Is this true for every model?"* — no; some models (particularly ones explicitly fine-tuned with a CLS-based objective, like certain Sentence-BERT variants) do use CLS pooling by design and perform well with it — check the model's actual training recipe rather than assuming one pooling strategy is universally superior.

### Q5 — A model card says to prefix queries with "query: " and passages with "passage: ". What happens if you skip this?
**Answer:** The model was trained with these prefixes as part of its instruction-tuning, rotating the output vector into task-appropriate subspaces; skipping them, or applying them inconsistently between ingestion and query time, measurably degrades retrieval quality because query and passage vectors are no longer in the geometric relationship the contrastive training established.
**Follow-up trap:** *"How would you catch this bug in practice?"* — it's silent — nothing errors, results just look subtly worse. Catch it via a recall@k regression test in CI that runs against a small fixed eval set on every embedding-pipeline change, not by manual inspection.

### Q6 — When would you choose an open-weight model like BGE-M3 over an API model?
**Answer:** When per-token API cost at your embedding volume outweighs the ops cost of self-hosting, when data residency/compliance forbids sending raw text to a third-party API, or when you need to fine-tune the embedding model on domain-specific data (which API-only models don't allow). BGE-M3 specifically adds value when you want dense, sparse, and multi-vector retrieval unified in one model rather than running separate systems.
**Follow-up trap:** *"What's the hidden cost people underestimate?"* — GPU serving infrastructure: batching, autoscaling under load, and pinning a specific model version so embeddings stay comparable across ingestion runs; this is a genuine ongoing platform commitment, not a one-time setup cost.

### Q7 — How does hard-negative mining during training affect which embedding model you should pick for a specialized domain?
**Answer:** A model's retrieval quality ceiling depends heavily on the quality of hard negatives (lexically similar, semantically different passages) it saw during contrastive training. A smaller model fine-tuned on domain-specific hard negatives (legal, biomedical, code) frequently outperforms a larger general-purpose model on that domain, because the general model never learned the domain's specific disambiguation boundaries.
**Follow-up trap:** *"So should you always fine-tune?"* — only if you have a labeled or synthetically-generated in-domain dataset and the volume to justify it; fine-tuning without enough quality hard-negative data can make a model worse, not better, and the eval discipline required is nontrivial.

### Q8 — Your team wants to switch from OpenAI text-embedding-3-small to Cohere embed-v4 for better multilingual coverage. What does this actually require?
**Answer:** A full reindex — re-embed every existing chunk with the new model (since the vector spaces are incompatible), rebuild the ANN index against the new vectors, and run a shadow evaluation comparing recall@k and answer quality against the old pipeline before cutting traffic over. This is not a config change; budget it as a migration project with its own compute and validation timeline.
**Follow-up trap:** *"Can you do a rolling migration to avoid downtime?"* — yes, but it requires running two indexes in parallel (old model's index serving live traffic, new model's index being built and shadow-evaluated) and a defined cutover point, not a gradual per-document swap, since a single query can't mix similarity scores from two incompatible spaces.

### Q9 — What's the actual mechanism by which Matryoshka truncation degrades gracefully instead of catastrophically?
**Answer:** The training loss is applied at multiple nested prefix lengths simultaneously, forcing gradient updates to push the most discriminative signal into the earliest dimensions across all training examples. This is fundamentally different from training only on the full vector and truncating post-hoc, which would discard information distributed arbitrarily across all dimensions rather than concentrated toward the front.
**Follow-up trap:** *"If I truncate a normal (non-MRL) embedding's dimensions, what happens?"* — unpredictable, often severe degradation, because there was never any training pressure to concentrate signal in a prefix; don't assume any embedding can be truncated safely without verifying it was trained with an MRL-style objective.

### Q10 — How would you decide the dimension to actually deploy for a given corpus?
**Answer:** Build a small labeled eval set (queries with known-relevant chunks), embed the corpus at several candidate dimensions via truncation, measure recall@k (and nDCG if ranking order matters) at each, and pick the smallest dimension where the metric plateaus — not the largest dimension available, and not a number chosen from a blog post.
**Follow-up trap:** *"What if you don't have labeled data yet?"* — generate a synthetic eval set (LLM-generated questions against known source chunks, see `10-rag-eval.md`) rather than skipping the measurement entirely; guessing a dimension without any eval is the actual failure mode interviewers are probing for.

### Q11 — Why might quantization (int8, binary) hurt recall more unpredictably than Matryoshka truncation?
**Answer:** Matryoshka's degradation is trained-in and validated by the model's own loss function across nested lengths; quantization is typically applied post-hoc to an already-trained embedding space, with no guarantee the model's geometry tolerates coarse binning evenly across dimensions or across different embedding models. Some models' vector distributions quantize cleanly; others lose meaningful recall at even mild quantization levels.
**Follow-up trap:** *"So would you ever combine Matryoshka truncation and quantization?"* — yes, this is common in production for extreme storage savings, but each stacked compression step needs its own recall@k validation on your corpus — don't assume the losses are simply additive or that one technique's safety margin covers the other.

### Q12 — Design the embedding strategy for a RAG system that must serve both English and low-resource-language queries against a shared corpus, under a strict per-query latency budget.
**Testing:** synthesis across model choice, multilingual coverage, and latency.
**Answer:** Start by checking a genuinely multilingual model's per-language coverage (not its aggregate MTEB/MIRACL score) against your actual target languages, since coverage is uneven and often English/Chinese/Spanish-weighted even in "multilingual" models — BGE-M3 or Cohere embed-v4 are reasonable starting candidates given their MIRACL performance. For the latency budget, self-host a Matryoshka-truncated, moderately-sized version of the query-embedding path (query embedding is on the critical path; passage embedding is not) rather than taking a network round trip to an API on every query. Validate low-resource-language recall specifically with an eval set in those languages — don't extrapolate from English performance.
**Follow-up trap:** *"What if the low-resource language just doesn't retrieve well no matter the model?"* — this is a real, current limitation (see `12-multilingual.md`); the honest answer is to consider translation-based retrieval (translate query to a well-supported pivot language before embedding) as a fallback, and to say so explicitly rather than implying every model handles every language equally.

---

## Red flags that fail you

- Comparing cosine similarity scores across two different embedding models as if they're on the same scale.
- Claiming any embedding vector can be truncated to fewer dimensions safely, without knowing whether the model was trained with a Matryoshka-style objective.
- Treating an embedding model switch as a config change rather than a full reindex-and-migrate project.
- Picking a model solely by its aggregate MTEB score without validating on the actual target corpus and languages.
- Not knowing that instruction/prefix conventions exist and that skipping them silently degrades quality.
- Assuming "multilingual" model cards imply uniform quality across all claimed languages.

---

## Cheat card

```
LINEAGE   TF-IDF/BM25 (lexical only) -> word2vec/GloVe (static, one vec/word)
          -> BERT (contextual, poor pooling for retrieval) -> Sentence-BERT
          (contrastive fine-tune, bi-encoder) -> modern API/open embedding models

BI-ENCODER  embed corpus offline once, embed query at request time (cheap).
            Cross-encoder = joint scoring, reserved for reranking small sets.

MRL (Matryoshka)  loss applied at multiple nested prefix lengths during training
            -> truncate + renormalize at inference, no retrain needed
            OpenAI: dimensions= param. Cohere: output_dimension.
            Models: OpenAI 3-*, Cohere embed-v4, Voyage-3.5, Gemini Emb2, Nomic v1.5

MTEB (2026, rough)  Cohere embed-v4 ~65.2 · OpenAI 3-large ~64.6 · BGE-M3 ~63.0
            -- ~2pt spread rarely decides outcomes; run your own eval

PRICING (2026)  OpenAI 3-small $0.02/1M tok · 3-large $0.13/1M tok, 3072d
            Cohere embed-v4 $0.12/1M tok, 128K ctx, matryoshka 256-1536
            BGE-M3 (open) 568M params, 100+ langs, 8192 ctx, dense+sparse+multivec

MEMORY  10M chunks @ 1536d fp32 = 61.4 GB raw vectors (before index overhead)
        -> truncate to 512d: 20.5 GB (~3x smaller, small recall cost)

PREFIXES  instruction-tuned models (E5-instruct, BGE-instruct) need consistent
          query:/passage: prefixes -- silent quality bug if skipped/inconsistent

MODEL SWITCH = FULL REINDEX  incompatible vector spaces across models/versions;
          budget as a migration project, shadow-eval before cutover

PICK ORDER  1) does it cover your target languages/domain (test, don't trust MTEB)
            2) self-host vs API (ops cost vs per-token cost)
            3) dimension via eval-driven Matryoshka truncation, not defaults
```

## Sources

- [10 Best Embedding Models 2026: Complete Comparison Guide — Openxcell](https://www.openxcell.com/blog/best-embedding-models/) — accessed 2026-07-27
- [Voyage 3.5 vs OpenAI vs Cohere Embedding Models 2026 — BuildMVPFast](https://www.buildmvpfast.com/blog/best-embedding-model-comparison-voyage-openai-cohere-2026) — accessed 2026-07-27
- [Cohere Embed v3: Multilingual Embedding Model Specs & Benchmarks (2026) — UC Strategies](https://ucstrategies.com/news/cohere-embed-v3-multilingual-embedding-model-specs-benchmarks-2026/) — accessed 2026-07-27
- [Which Embedding Model Should You Actually Use in 2026? — Cheney Zhang](https://zc277584121.github.io/rag/2026/03/20/embedding-models-benchmark-2026.html) — accessed 2026-07-27
- [BGE-M3: Multilingual Bi-Encoder Model — Emergent Mind](https://www.emergentmind.com/topics/bge-m3-model) — accessed 2026-07-27
- [The Best Open-Source Embedding Models in 2026 — BentoML](https://www.bentoml.com/blog/a-guide-to-open-source-embedding-models) — accessed 2026-07-27
- Matryoshka Representation Learning, Kusupati et al., NeurIPS 2022 (arXiv:2205.13147)
- Sentence-BERT, Reimers & Gurevych, EMNLP 2019 (arXiv:1908.10084)

## Changelog
- 2026-07-27 — created
