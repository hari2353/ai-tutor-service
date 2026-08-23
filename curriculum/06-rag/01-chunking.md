# Chunking: Fixed, Recursive, Semantic, Contextual, Late

> **Track:** T06 RAG (Retrieval-Augmented Generation) · **Time:** 2h · **Prereqs:** embeddings basics (05-llm-internals) · **Updated:** 2026-07-26
> **Module id:** `T06-chunking` · **Tags:** sprint, ingest
> **Lab:** `labs/py/08-chunking/` · `labs/ts/01-chunking/`

## The 30-second version

Chunking is the highest-leverage decision in a RAG pipeline because it happens before retrieval and generation, so every downstream metric — recall@k, reranker precision, hallucination rate — is bounded by whether the chunk boundary preserved the answer. Recursive, structure-aware splitting (LangChain/LlamaIndex default) is the right starting point for almost everything; fixed-size-with-overlap is fine for short, uniform text; semantic chunking earns its extra embedding calls only when topical boundaries genuinely vary within a doc; contextual retrieval (Anthropic, Sept 2024) fixes the "who is 'the company'" decontextualization problem cheaply because prompt caching makes the per-chunk LLM call affordable; late chunking fixes the same problem without any LLM call, but only if your embedding model has a long enough context window to see the whole document first. None of these numbers are universal — pick chunk size empirically against a recall@k eval set built from your own corpus and query distribution, not from a blog post default.

## Why this gets asked

The interviewer has watched a RAG demo work perfectly on three example queries and then fail in front of a customer because the real chunk boundary split the answer across two vectors, or because a chunk like "revenue grew 3% over the previous quarter" retrieved fine on its own embedding but meant nothing to the LLM without knowing which company and quarter. They want to hear you reason about *why* a chunking choice fails for a specific corpus shape, not recite "512 tokens with 50 overlap" as gospel.

---

## Lineage: past → present → future

**What came before.** Classical IR chunked at paragraph or sentence boundaries purely for BM25 indexing, where a chunk is just a scored bag of terms and coherence doesn't matter much. Early RAG systems (2022–2023, first LangChain/LlamaIndex releases) inherited naive fixed-length character splitting from that world and bolted it onto embeddings, which care about semantic coherence in a way BM25 never did. The pain: fixed-length splits cut mid-sentence and mid-table, so the embedding of a truncated fragment drifted away from the topic it was supposed to represent, and answers that spanned a chunk boundary became unretrievable no matter how good the embedding model was.

**Where it stands now.** Recursive, separator-aware splitting (try paragraph breaks, then sentence breaks, then whitespace, in that order) is the default in both LangChain and LlamaIndex and is what almost every production system ships first, because it approximates document structure without needing a model call. Anthropic's Contextual Retrieval (published Sept 19, 2024) is the most widely adopted fix for the decontextualization problem specifically because prompt caching makes generating context for every chunk cost about $1.02 per million document tokens — cheap enough to run at ingest time across an entire corpus. Semantic chunking (embedding-similarity breakpoints) and late chunking (Jina AI, arXiv:2409.04701, also Sept 2024) are both used, but more selectively: semantic chunking costs an embedding call per sentence pair, and late chunking needs a long-context embedding model to look at the whole document before pooling per-chunk vectors. The live disagreement is whether contextual retrieval's per-chunk LLM call is worth it versus just using bigger chunks and leaning harder on a reranker — both approaches show up in production, and the honest answer is "it depends on how variable your document structure is and whether you already have prompt caching wired up."
Anthropic itself makes the point that these techniques are for knowledge bases that don't fit in context. Their guidance: if the knowledge base is under 200,000 tokens (~500 pages), skip RAG entirely and put the whole thing in the prompt, especially now that prompt caching cuts the cost of doing so by up to 90%.

**Where it's heading.** Embedding models are trending toward longer native context (8k+ tokens is now common), which pushes late chunking toward becoming the default rather than a specialty technique, since it gets contextual quality without an extra LLM call — moderate confidence. Layout-aware, ML-driven document parsers (Unstructured, LlamaParse) are converging on treating "chunking" and "parsing" as one step rather than two, because table and figure boundaries are a parsing problem before they're a chunking problem — this is shipping now, not speculative. More speculative: agentic RAG stacks where the retrieval granularity is decided at query time by a model rather than fixed at ingest time (query the corpus at the paragraph level first, then request the surrounding section if needed) — this exists in a handful of 2026 agentic frameworks but is not yet a settled pattern.

---

## Mental model

Chunking strategies sit on two mostly-independent axes: how you decide *where* to cut, and how you inject the surrounding context that the cut destroys.

```
              inject context?
                    │
       late          │      contextual
     chunking ───────┼──────  retrieval
   (embed whole doc   │    (LLM-generated
    THEN pool)        │     context prepended)
                      │
   ───────────────────┼─────────────────────  no extra context
     fixed / recursive│      semantic
      (cheap, cuts on │   (cuts on meaning,
       structure)     │    still decontextualized)
                    where to cut?
        naive/structural ──────────► meaning-aware
```

Fixed and recursive splitting answer "where do I cut" cheaply using structure (paragraph, sentence, function boundary) and do nothing about the information lost at the boundary. Semantic chunking spends more compute to answer "where do I cut" using meaning instead of structure, but a semantically clean chunk can still be decontextualized ("the company," "it," "this quarter"). Contextual retrieval and late chunking both attack the *context* axis: contextual retrieval bolts context on after the fact with an LLM; late chunking never loses it in the first place because the whole document is embedded before any splitting happens.

---

## How it actually works

### 1. Fixed-size with overlap

Split by raw character or token count, sliding a window with overlap so an answer straddling a boundary in one chunk fully appears in the neighbor.

```python
def fixed_chunks(text: str, size: int = 1000, overlap: int = 150):
    step = size - overlap
    return [text[i:i + size] for i in range(0, len(text), step)]
```

LangChain's base `TextSplitter` defaults to `chunk_size=4000` characters and `chunk_overlap=200` — roughly 5% overlap — which is a reasonable character-level default but almost nobody ships it unmodified, because 4000 characters (~800–1000 tokens) is oversized for embedding models with a 512-token input cap (most `sentence-transformers`/BGE-family models). In practice, teams pick a **token** count, not a character count, and size it to the embedding model's limit, not the LLM's.

### 2. Recursive character splitting

Tries a priority list of separators, falling back to a finer one only where a chunk still exceeds `chunk_size`:

```python
# LangChain's default separator order
DEFAULT_SEPARATORS = ["\n\n", "\n", " ", ""]
```

This is why it's the default: it approximates "keep paragraphs together, then sentences, then words" without needing a model call, and LangChain ships language-aware separator lists (`Language.PYTHON` splits before `class`/`def`, `Language.MARKDOWN` splits on heading levels, `Language.JAVA` splits before `class`/`public`/`private`) so structured text degrades gracefully instead of getting cut at an arbitrary character offset.

### 3. Semantic (embedding-based) chunking

Embed consecutive sentences, compute cosine similarity between neighbors, and cut where similarity drops below a percentile threshold — a sharp drop signals a topic shift.

LlamaIndex's `SemanticSplitterNodeParser` defaults to `buffer_size=1` (how many neighboring sentences to group before comparing) and `breakpoint_percentile_threshold=95` (only the most severe 5% of similarity drops become cut points). This produces variable-length chunks: dense, single-topic sections stay whole; rapidly shifting text gets cut more often. Cost: one embedding call per sentence (or sentence group) at ingest time, versus zero extra calls for recursive splitting — this is the tradeoff that keeps it from being the universal default.

### 4. Contextual Retrieval (Anthropic, Sept 2024)

Prepend a short, LLM-generated situating sentence to each chunk *before* embedding it and *before* building the BM25 index:

```
original_chunk = "The company's revenue grew by 3% over the previous quarter."

contextualized_chunk = "This chunk is from an SEC filing on ACME Corp's
performance in Q2 2023; the previous quarter's revenue was $314 million.
The company's revenue grew by 3% over the previous quarter."
```

The context (usually 50–100 tokens) is generated per chunk with a prompt that shows the model the whole document and the chunk, and asks for a succinct situating sentence — Anthropic's reference implementation uses Claude 3 Haiku for this. Measured results (top-20-chunk retrieval failure rate, i.e. 1 − recall@20, averaged across codebases, fiction, ArXiv and science papers):

| Configuration | Failure rate | Reduction |
|---|---|---|
| Baseline (embeddings only) | 5.7% | — |
| + Contextual Embeddings | 3.7% | 35% |
| + Contextual Embeddings + Contextual BM25 | 2.9% | 49% |
| + both, reranked (Cohere reranker, top-150→top-20) | 1.9% | 67% |

Cost, with prompt caching (the whole document is cached once, not re-sent per chunk): **$1.02 per million document tokens**, assuming 800-token chunks, 8k-token documents, 50 tokens of instruction, 100 tokens of generated context per chunk. Without prompt caching this is far more expensive, because the whole document would be re-sent to the LLM for every single chunk.

### 5. Late chunking (Jina AI, arXiv:2409.04701)

Inverts the order: embed the *entire* document first with a long-context embedding model (jina-embeddings-v2/v3, nomic-embed-text-v1 all support up to 8k input tokens), producing one token-embedding per input token with full document context baked in by self-attention. Only then split into chunks — chunk embeddings are the **mean pool of the token embeddings that fall inside that chunk's span**. No LLM call, no training. The chunk embedding for "the company's revenue grew" already carries the attention-weighted influence of "ACME Corp" and "Q2 2023" from earlier in the document, because the whole document was encoded together before pooling. Evaluations show late chunking outperforms naive per-chunk embedding on jina-embeddings-v2-small, jina-embeddings-v3 and nomic-embed-text-v1.

### 6. Tables, code, and PDFs

Naive text extraction flattens tables into a run-on string that loses row/column alignment — the classic silent failure. Layout-aware parsers fix this by analyzing the visual structure before extracting text:

- **Unstructured** (open-source library + managed API, ML layout analysis via detectron2) is the general-purpose industry standard for mixed-format extraction, and its `chunk_by_title` strategy keeps content under a heading together instead of cutting on raw length.
- **LlamaParse** uses vision-based layout analysis and is the stronger choice specifically for complex tables (merged cells, borderless tables), though quality is still inconsistent on the hardest layouts.
- Both typically serialize tables to Markdown so the LLM sees column headers next to their values instead of a wall of numbers.
- **Code** should never be split by character count — use the language-aware recursive separators (split before `class`/`def`/`function` boundaries) so a chunk never ends mid-function.

### Chunk-size guidance, with the reasoning

Two failure modes pull in opposite directions, and chunk size is where you trade one for the other:

- **Too large** → the embedding "over-compresses": a 2000-token chunk covering three subtopics produces one vector that's an average of all three, and a query about the second subtopic scores lower cosine similarity than it would against a focused chunk, because the vector is diluted by the other two-thirds of the text.
- **Too small** → you lose the anchor context (pronouns, "the company," a table's header row, a function's enclosing class) and retrieval returns technically-correct-but-useless fragments — this is exactly the failure contextual retrieval and late chunking exist to fix.

Starting points, to be validated against your own recall@k eval, not shipped blind:

| Corpus shape | Starting chunk size | Why |
|---|---|---|
| FAQ / support tickets | 200–500 tokens | Answer usually lives in one paragraph; small chunks keep precision high |
| Narrative / legal / financial filings | 800–1000 tokens | Meaning depends on surrounding clauses; over-splitting destroys it |
| Code | one function/class per chunk (language-aware split, not token count) | Splitting mid-function guarantees an unusable retrieval |
| Overlap | 10–20% of chunk size | Enough to avoid severing a sentence at the boundary without meaningfully inflating storage |

---

## Build it from scratch

```python
# untested sketch — illustrates the mechanics, not production-hardened
import re

def recursive_split(text: str, chunk_size: int, separators: list[str]) -> list[str]:
    if len(text) <= chunk_size or not separators:
        return [text]
    sep, rest = separators[0], separators[1:]
    parts = text.split(sep) if sep else list(text)
    chunks, current = [], ""
    for part in parts:
        candidate = current + (sep if current else "") + part
        if len(candidate) <= chunk_size:
            current = candidate
        else:
            if current:
                chunks.append(current)
            # part itself may still be too long — recurse with a finer separator
            chunks.extend(recursive_split(part, chunk_size, rest))
            current = ""
    if current:
        chunks.append(current)
    return chunks


def late_chunk(token_embeddings: "np.ndarray", spans: list[tuple[int, int]]):
    """token_embeddings: (seq_len, dim) from a long-context encoder run over
    the WHOLE document. spans: character/token offsets of each chunk.
    Returns one pooled vector per chunk, each carrying whole-doc context."""
    return [token_embeddings[start:end].mean(axis=0) for start, end in spans]


def contextualize_chunk(llm_call, document: str, chunk: str) -> str:
    """One prompt-cached call per chunk; document is cached once per doc."""
    prompt = (
        f"<document>\n{document}\n</document>\n"
        f"Here is the chunk we want to situate within the whole document\n"
        f"<chunk>\n{chunk}\n</chunk>\n"
        "Give a short succinct context to situate this chunk within the "
        "overall document for search retrieval purposes. Answer only with "
        "the context."
    )
    context = llm_call(prompt, cache_prefix=document)  # cache_prefix hits the KV cache
    return f"{context}\n\n{chunk}"
```

---

## How it's done in production

**Frameworks**: LangChain (`RecursiveCharacterTextSplitter`, `TokenTextSplitter`), LlamaIndex (`SentenceSplitter`, `SemanticSplitterNodeParser`, `MarkdownNodeParser`). **Parsing**: Unstructured (open-source + API) for general mixed-format extraction, LlamaParse for vision-based complex-table extraction. **Contextual retrieval**: Anthropic's cookbook implementation using Claude with prompt caching; the same pattern is portable to any LLM with prompt/context caching. **Late chunking**: Jina's long-context embedding models expose this natively; Weaviate has documented integration patterns for it.

| Symptom | Cause | Fix |
|---|---|---|
| Retrieved chunk scores high similarity but answers the wrong sub-question | Chunk boundary split the answer across two vectors, or chunk covers multiple subtopics (over-compression) | Reduce chunk size or switch to semantic chunking; increase overlap |
| LLM says "I don't know which company/quarter this refers to" despite retrieving the right chunk | Decontextualized chunk — pronouns/references point outside the chunk | Contextual retrieval or late chunking |
| Table numbers appear in the wrong column, or scrambled entirely | Naive text extraction flattened the table's 2D structure into a 1D string | Layout-aware parser (Unstructured/LlamaParse), serialize to Markdown tables |
| Code search returns half a function | Character-count split crossed a function/class boundary | Language-aware recursive separators (`Language.PYTHON`, etc.) |
| Eval recall@k looks great, production complaints roll in anyway | Eval doc lengths don't match production doc lengths; fixed chunk_size tuned to short eval docs breaks on long real documents | Chunk by structure (headings/sections) instead of a fixed length; rebuild eval set from real production documents |
| Ingest cost/latency balloons after adding contextual retrieval | Contextual retrieval implemented without prompt caching — full document re-sent per chunk | Verify prompt/context caching is actually being hit; check cache-hit metrics, not just that caching is "enabled" |

---

## Tradeoffs & when NOT to use it

- **Don't use RAG/chunking at all if the corpus is small.** Anthropic's own guidance: under ~200,000 tokens (~500 pages), just put the whole thing in a cached prompt. Chunking exists to solve a scaling problem you may not have.
- **Semantic chunking is not strictly better** — it costs one embedding call per sentence at ingest time, and on short, uniform documents (a single FAQ answer, a short support ticket) it buys nothing over a simple paragraph split while adding latency and non-determinism to the pipeline.
- **Contextual retrieval is wasted effort on already-self-contained chunks** — a chunk that already names its subject ("ACME Corp's Q2 2023 revenue grew 3%") gets no benefit from a prepended context sentence; profile your failure cases before assuming you need it.
- **Late chunking requires a long-context embedding model.** It cannot be retrofitted onto a 512-token encoder — the whole point is encoding the full document before pooling, so if your embedding model caps at 512 tokens, this technique is unavailable to you until you switch models.
- **Don't chase the smallest possible chunk size for precision.** Smaller chunks multiply index size, multiply the number of chunks a reranker has to score, and increase the chance that any single retrieved chunk lacks the surrounding context to be useful on its own — precision at the vector-similarity level is not the same as usefulness to the LLM.

---

## Interview questions

### Q1 — Why chunk at all instead of embedding whole documents?
**Testing:** baseline understanding of the embedding bottleneck.
**Answer:** Embedding models compress a fixed-size input into a fixed-size vector; a whole 50-page document averaged into one vector loses almost all specific detail, so a query about page 30 won't score well against it. Chunking keeps each vector focused enough that similarity search can localize the right passage. It also bounds how much text you stuff into the LLM's context per retrieved item.
**Follow-up trap:** *"So why not just chunk as small as possible?"* — smaller chunks lose surrounding context (pronouns, headers, cross-references) and multiply storage and reranker cost; there's a floor below which precision gains reverse into unusability.

### Q2 — How do you actually pick a chunk size for a new corpus?
**Testing:** whether the candidate treats this as an empirical decision or a memorized number.
**Answer:** Start from the document shape (FAQ-like → 200–500 tokens; narrative/legal → 800–1000 tokens), build a recall@k eval set from real questions against real documents, then sweep chunk size and overlap against that eval before shipping. The "right" number is a property of the eval's failure mode, not a universal constant.
**Follow-up trap:** *"What if you don't have an eval set yet?"* — say you'd build one from a small labeled sample before making the decision, not ship a default and hope; naming "512 tokens" with no justification is a red flag interviewers are listening for.

### Q3 — What does overlap actually buy you, and what does it cost?
**Answer:** Overlap prevents an answer that straddles a chunk boundary from being split across two vectors, neither of which fully contains it. Cost: storage and embedding compute scale with `chunk_size / (chunk_size − overlap)`, so 20% overlap means roughly 25% more chunks than no overlap for the same document.
**Follow-up trap:** *"Does more overlap always help recall?"* — no, past a point you're mostly re-embedding duplicate text and diluting the corpus with near-identical vectors, which can actually hurt because near-duplicates compete for the same top-k slots.

### Q4 — Explain contextual retrieval and why it works.
**Answer:** Prepend a short LLM-generated sentence to each chunk, before embedding and before BM25 indexing, that names what the chunk is about in the context of the whole document. It works because chunks are frequently decontextualized ("the company grew 3%") and the prepended sentence restores the missing anchor for both the lexical (BM25) and semantic (embedding) retrieval legs. Anthropic measured a 49% reduction in top-20 retrieval failures combining both legs, 67% with reranking added.
**Follow-up trap:** *"Isn't that expensive — an LLM call per chunk?"* — it's cheap specifically because of prompt caching: the whole document is cached once and only referenced, not re-sent, per chunk, bringing cost to about $1.02 per million document tokens. Without caching, say so plainly — it would be far more expensive.

### Q5 — What's late chunking and how does it differ from contextual retrieval?
**Answer:** Late chunking embeds the whole document first with a long-context model, then mean-pools token embeddings within each chunk's span — context is baked in by attention before pooling, with zero extra LLM calls. Contextual retrieval instead generates an explicit text sentence via an LLM and prepends it before a normal per-chunk embedding call. Late chunking is cheaper per-document (no LLM call) but requires a long-context embedding model; contextual retrieval works with any embedding model but costs an LLM call per chunk (mitigated by caching).
**Follow-up trap:** *"Can you combine them?"* — yes in principle, but there's little published evidence they stack additively, and you'd be paying both costs; treat this as untested territory rather than asserting a number.

### Q6 — How do you chunk a table without breaking it?
**Answer:** Never let plain-text extraction flatten a table — use a layout-aware parser (Unstructured or LlamaParse) that recognizes the table structure and serializes it to Markdown, keeping column headers adjacent to their values. Chunk at table boundaries, not mid-table, and consider keeping small tables whole as a single chunk regardless of token count.
**Follow-up trap:** *"What about tables that don't fit in one chunk?"* — repeat the header row in each continuation chunk so every chunk is independently interpretable; this is the table-specific version of the "decontextualization" problem.

### Q7 — How do you chunk source code?
**Answer:** Use language-aware separators that split before class/function/method boundaries (LangChain's `Language.PYTHON`, `Language.JAVA`, etc.), never raw character count, because a function split in half is unusable regardless of similarity score.
**Follow-up trap:** *"What if a single function is huge?"* — fall back to splitting at nested boundaries (inner functions, logical blocks) rather than an arbitrary character count, and accept that very large functions may need a summary chunk plus the full body as a secondary retrievable unit.

### Q8 — What is semantic chunking and when would you not use it?
**Answer:** Embed consecutive sentences, compute cosine similarity between neighbors, and cut where similarity drops below a percentile threshold (LlamaIndex defaults to the 95th percentile with a buffer of 1 sentence) — a sharp similarity drop signals a topic shift. Skip it on short, uniform documents (FAQ entries, tickets) where there's no real topic drift to detect, since it adds an embedding call per sentence for no measurable gain there.
**Follow-up trap:** *"Is it deterministic?"* — the breakpoints depend on the embedding model and threshold, so re-running with a different model can shift boundaries; don't claim it's a stable, reproducible chunking scheme across model versions.

### Q9 — Your recall@20 looks great in eval, but production users complain retrieval is missing obvious answers. Diagnose it.
**Answer:** Most likely a distribution mismatch — the eval set was built from short, well-formed documents while production documents are longer or structured differently, and a fixed chunk_size tuned to the eval set doesn't generalize. Rebuild the eval from real production documents and real user queries (including the messy ones), and prefer structural chunking (by heading/section) over a fixed length that only worked by coincidence on the eval set.
**Follow-up trap:** *"Could it be an indexing bug instead?"* — yes, always rule out a stale index or a chunking pipeline that silently dropped documents (check ingest counts) before concluding it's a chunk-size problem.

### Q10 — Walk me through the cost of running contextual retrieval over a 10-million-token corpus.
**Answer:** At $1.02 per million document tokens (with prompt caching, per Anthropic's published figures), that's roughly $10.20 total for a one-time ingest pass. Cheap in absolute terms; the number to watch instead is whether your cache is actually being hit — if the caching layer isn't configured correctly and the full document is resent per chunk, costs and latency both increase by an order of magnitude or more.
**Follow-up trap:** *"Does this repeat on every reindex?"* — yes, contextual retrieval is a preprocessing step that must be rerun whenever chunk boundaries or the document changes; factor that into how often you expect to reindex.

### Q11 — When is plain fixed-size splitting actually fine?
**Answer:** Short, structurally uniform text where sentence/paragraph boundaries don't matter much for meaning — log lines, short transcripts, uniformly formatted records — and where the cost of recursive or semantic splitting isn't justified by any measurable recall gain.
**Follow-up trap:** *"So why doesn't everyone just use fixed-size for simplicity?"* — because most real corpora (docs, contracts, code, support tickets) have exploitable structure, and ignoring it costs you exactly the boundary-splitting failures this module is about.

### Q12 — Late chunking needs which kind of embedding model, specifically?
**Answer:** A long-context model capable of ingesting the entire source document in one forward pass (jina-embeddings-v2/v3, nomic-embed-text-v1 support up to ~8k tokens) — the technique embeds the whole document before pooling, so the model's max sequence length must cover the document length, not just the chunk length.
**Follow-up trap:** *"What happens for a document longer than the model's max context?"* — you're back to splitting the document into sections first (losing some cross-section context) and applying late chunking within each section — the benefit shrinks proportionally.

### Q13 — How does chunk size interact with reranker cost?
**Answer:** Rerankers (cross-encoders) score every candidate chunk against the query, so cost and latency scale roughly linearly with the number of chunks reranked, not their size. Smaller chunk sizes mean more chunks per document at a given top-k retrieval depth, which directly increases reranker load; this is a real cost coupling between the chunking decision made at ingest time and the reranking budget spent at query time.
**Follow-up trap:** *"So bigger chunks are always cheaper?"* — no, bigger chunks reduce reranker count but increase the token cost of the context window if those chunks are passed to the LLM, and increase the risk of the over-compression failure mode. It's a genuine three-way tradeoff, not a free win.

### Q14 — A candidate says "I always use the smallest possible chunk size for maximum precision." What's wrong with that?
**Answer:** Ignores that below a certain size, chunks lose the surrounding context needed to be independently interpretable (the decontextualization problem), multiplies index storage and reranker load, and increases near-duplicate competition for top-k slots from overlapping tiny chunks. There is no universally "maximum precision" chunk size — it's a tradeoff surface, and the right point on it is corpus-dependent.
**Follow-up trap:** *"What would you say instead in an interview?"* — state the tradeoff explicitly and name the eval-driven process you'd use to find the right point, which is exactly the senior signal this question is fishing for.

### Q15 — Design a chunking strategy for a corpus of legal contracts with embedded financial tables and heavy cross-referencing ("as defined in Section 4.2").
**Testing:** synthesis across everything in this module.
**Answer:** Parse with a layout-aware tool (Unstructured or LlamaParse) so tables are extracted as structured Markdown rather than flattened text. Chunk by section/clause boundary (structural, not fixed-length) since legal meaning is clause-scoped. Apply contextual retrieval on top, since cross-references ("Section 4.2") are exactly the decontextualization failure it fixes — the generated context can resolve "as defined in Section 4.2" to what that section actually says. Keep small tables whole as single chunks with repeated headers if they must span multiple chunks. Validate all of it against a recall@k eval built from real contract questions before tuning further, and expect chunk size to land near the 800–1000 token range given the density of legal prose.
**Follow-up trap:** *"Would you also consider late chunking here instead of contextual retrieval?"* — only if you have a long-context embedding model and want to avoid the LLM-call cost; the cross-reference resolution problem is served by either, but late chunking needs the model capability and contextual retrieval needs the caching infrastructure — pick based on what you already have deployed.

---

## Red flags that fail you

- Naming a chunk size with no reasoning tied to corpus shape or an eval.
- Claiming semantic chunking is strictly better than recursive splitting.
- Not knowing contextual retrieval's affordability depends on prompt caching.
- Treating tables as plain text with no mention of layout-aware parsing.
- Splitting code by character count instead of language-aware boundaries.
- Believing smaller chunks are always more precise.
- Confusing late chunking (embed-then-pool) with contextual retrieval (LLM-generated prepended text) — they solve the same problem by opposite mechanisms.

---

## Cheat card

```
RECURSIVE SPLIT   default separators: ["\n\n","\n"," ",""]; language-aware for code/markdown
                  LangChain base defaults: chunk_size=4000 chars, chunk_overlap=200 (character-level;
                  most teams override to token counts sized to the embedding model's limit)

SEMANTIC CHUNK    LlamaIndex SemanticSplitterNodeParser: buffer_size=1, breakpoint_percentile=95
                  cost: 1 embedding call per sentence/group — skip on short uniform docs

CONTEXTUAL RETR.  Anthropic, Sept 2024. Prepend 50-100 token LLM-generated context before embed + BM25.
                  Failure rate: 5.7% -> 2.9% (49% cut, +BM25) -> 1.9% (67% cut, +rerank top150->20)
                  Cost: $1.02 / million doc tokens WITH prompt caching. Model used: Claude 3 Haiku.

LATE CHUNKING     Jina AI, arXiv:2409.04701. Embed WHOLE doc first (long-context model, ~8k tokens:
                  jina-v2/v3, nomic-embed-text-v1), THEN mean-pool token embeddings per chunk span.
                  No LLM call. Requires long-context embedding model.

TABLES/CODE       Unstructured (general, detectron2 layout) / LlamaParse (best complex tables, vision-based)
                  serialize tables to Markdown. Code: split before class/def/function, never by char count.

CHUNK SIZE        FAQ/support: 200-500 tok · narrative/legal: 800-1000 tok · code: 1 func/class per chunk
                  overlap: 10-20% of chunk size · ALWAYS validate against recall@k eval, not a default

RAG NOT NEEDED    corpus < ~200k tokens (~500 pages): just cache the whole thing in the prompt
```

## Sources

- [Introducing Contextual Retrieval — Anthropic](https://www.anthropic.com/engineering/contextual-retrieval) — accessed 2026-07-26
- [Late Chunking: Contextual Chunk Embeddings Using Long-Context Embedding Models (arXiv:2409.04701)](https://arxiv.org/html/2409.04701v2) — accessed 2026-07-26
- [Late Chunking in Long-Context Embedding Models — Jina AI](https://jina.ai/news/late-chunking-in-long-context-embedding-models/) — accessed 2026-07-26
- [Late Chunking: Balancing Precision and Cost in Long Context Retrieval — Weaviate](https://weaviate.io/blog/late-chunking) — accessed 2026-07-26
- [Semantic Chunker — LlamaIndex documentation](https://docs.llamaindex.ai/en/v0.12.15/module_guides/loading/node_parsers/modules/) — accessed 2026-07-26
- [LangChain text-splitters source — `character.py`, `base.py`](https://github.com/langchain-ai/langchain/blob/master/libs/text-splitters/langchain_text_splitters/base.py) — accessed 2026-07-26
- [4 PDF Parsing Strategies for RAG, Part 2 — Unstructured](https://unstructured.io/blog/mastering-pdf-transformation-strategies-with-unstructured-part-2) — accessed 2026-07-26
- [Best PDF Parsers for AI and RAG Workflows in 2026 — Firecrawl](https://www.firecrawl.dev/blog/best-pdf-parsers) — accessed 2026-07-26

## Changelog
- 2026-07-26 — created
