# Structuring Source Data: Tables, Code, PDFs, Hierarchies, Knowledge Graphs

> **Track:** T06 RAG (Retrieval-Augmented Generation) · **Time:** 2.5h · **Prereqs:** 01-chunking · **Updated:** 2026-08-01
> **Module id:** `T06-data-structuring` · **Tags:** ingest

## The 30-second version

Chunking (`01-chunking`) assumes you already have clean, structurally-faithful text to split, and that assumption is the part of the pipeline that breaks first in production: a naive text extractor flattens a table into an unaligned string, interleaves two PDF columns into one nonsensical paragraph, or splits a function in half because it never knew the document had structure at all. Each source type has a specific, named failure and a specific fix — tables need row/column structure preserved (markdown serialization, per-row records, or a summary-plus-reference pattern depending on size), multi-column and scanned PDFs need layout-aware parsing with OCR fallback rather than blind text extraction, code needs AST-aware splitting on function/class boundaries rather than character counts, long cross-referential documents need parent-child hierarchical retrieval rather than one flat chunk size, and images need a captioning step because no text embedding model can see pixels. Knowledge graph extraction is the most expensive tool in this module — real entity/relationship structure that supports multi-hop reasoning flat chunks can't — and it earns its cost (historically tens of thousands of dollars to index a large corpus, now dropping fast, plus a measurable 2-3x query-time latency tax from graph traversal) only for corpora and query patterns that are genuinely relational, not as a default upgrade over chunking. The unifying principle: identify what kind of document you actually have before you chunk it, because chunking strategy is a downstream decision that a wrong upstream extraction step invalidates no matter how well-tuned it is.

## Why this gets asked

The interviewer has watched a RAG demo built entirely on clean markdown docs fail the moment it met a real enterprise corpus — scanned invoices, a financial report with fifteen embedded tables, a codebase, a 200-page policy manual with nested cross-references — and watched the team's first instinct be to tune chunk size, which does nothing when the actual bug is upstream in extraction. They want to know whether you diagnose data-structuring failures as a distinct pipeline stage before chunking, and whether you know the specific tool tradeoffs (layout-aware parser choice, when a knowledge graph is worth its cost) rather than reaching for one library and hoping it generalizes.

---

## Lineage: past → present → future

**What came before.** Early RAG pipelines (2022–2023) treated document ingestion as a solved problem inherited from classical text processing: run a plain-text extractor (PyPDF2, `pdfminer`) over whatever the source format was and hand the result straight to a text splitter, implicitly assuming every document was structurally equivalent to a clean `.txt` file. The pain was immediate and specific once real documents arrived: PDF text extraction reads in whatever internal object order the PDF encodes, which for a two-column layout frequently means alternating lines from the left and right columns rather than reading each column top-to-bottom — producing fluent-looking but semantically scrambled text with no error thrown, since nothing about the extraction *fails*, it just silently produces the wrong order. Tables fared even worse: flattening a table to plain text discards column alignment entirely, so a row like "Revenue | Q1 | $4.2M" becomes an unstructured run of tokens with no way to recover which number belonged to which column header. Code fed through the same generic splitters got cut at arbitrary character counts, routinely mid-function.

**Where it stands now.** Layout-aware, ML-driven parsers (Unstructured, LlamaParse, Docling, Marker-PDF) now treat parsing and chunking as one coupled problem rather than two: they run a layout-detection model (bounding boxes for paragraphs, tables, headers/footers, columns) before any text is extracted, so text extraction respects visual structure instead of raw byte order. There is real, documented variance between them — LlamaParse's "accurate" mode has a known reading-order weakness specifically on multi-column layouts, where text from adjacent columns can still interleave, while Docling and Marker-PDF are more commonly recommended for research papers and reports with genuinely complex multi-column layouts. For code, AST-aware chunking via `tree-sitter` (formalized as a retrieval-quality technique in work like cAST, arXiv:2506.15655) is the settled standard, splitting at syntactic boundaries rather than character counts. For long, internally cross-referential documents (policies, RFCs, technical manuals), hierarchical parent-child chunking with retrieval-time merging (LlamaIndex's `AutoMergingRetriever`: retrieve small leaf chunks by embedding similarity, then substitute the parent chunk when enough of its children are retrieved together) is the accepted answer to "small chunks lose context, big chunks over-compress" for this specific document shape. The least settled area is knowledge graphs: Microsoft's GraphRAG demonstrated real value for multi-hop and "global" (whole-corpus-summary) queries that flat retrieval structurally cannot answer, but its first published cost profile — tens of thousands of dollars to index a large corpus, entity/relation extraction inflating token usage 3-5x over plain chunking, and 2-3x higher end-to-end query latency from graph traversal and community summarization — kept it a specialist tool rather than a default, and that is actively changing as cost-reduction techniques mature.

**Where it's heading.** Cost-reduction research for knowledge-graph RAG is moving fast and is real, not speculative: Microsoft's own reporting shows GraphRAG indexing cost falling to roughly 0.1% of its original 2024 figure within about 18 months through better extraction prompting and caching, and techniques like LightRAG report roughly 60% lower indexing token cost with close to half the median query latency of naive GraphRAG, with KET-RAG cutting cost further by mixing a cheap keyword-bipartite graph with LLM-based extraction limited to a PageRank-selected subset of core chunks — moderate-to-high confidence this pushes knowledge-graph augmentation from "specialist, expensive" toward "occasionally the default for enterprise corpora with real relational structure" over the next few years, though the query-time latency tax hasn't dropped as fast as the indexing cost and remains a real constraint. Unified vision-language document models that output structured, retrieval-ready units directly (skipping a separate parse-then-chunk pipeline entirely) are shipping in research and early products (e.g. `dots.ocr`) — real but early, moderate confidence this becomes a standard ingestion pattern rather than today's separate best-of-breed parser plus splitter pipeline.

---

## Mental model

Everything in this module happens *before* `01-chunking` ever runs — chunking strategy is a downstream decision that a bad upstream extraction step invalidates no matter how well it's tuned:

```
  RAW SOURCE
     │
     ├── table?          → is row/column structure preserved, or flattened to a string?
     ├── PDF?             → single column (safe) or multi-column (reading-order risk)?
     │                       → born-digital (extractable text) or scanned (needs OCR)?
     ├── code?            → split on AST boundaries, or on raw character count?
     ├── long/hierarchical? → one flat chunk size, or parent-child with retrieval-time merge?
     ├── image/figure?    → captioned into text, or invisible to every text embedding model?
     └── highly relational? → flat chunks, or entity/relationship graph for multi-hop queries?
                                    │
                                    ▼
                          01-CHUNKING runs on the OUTPUT of this stage
                          (garbage structure in -> no chunk-size tuning fixes it)
```

The single unifying failure across every branch: a naive pipeline assumes the source is already equivalent to clean, linear plain text, and every one of these source types violates that assumption in a different, specific way.

---

## How it actually works

### Tables: why naive chunking destroys them, and the three fixes

Flattening a table to plain text produces a run-on string with no recoverable column alignment — a chunk containing "Revenue Q1 $4.2M Q2 $5.1M Expenses Q1 $3.0M Q2 $3.4M" gives an embedding model and an LLM no reliable way to know which number is which quarter's revenue versus expenses, and the resulting embedding is diluted across all of those numbers rather than representing any one relationship clearly.

- **Markdown serialization** (the default fix for small-to-medium tables): render the table as a markdown table with the header row repeated, which keeps columns aligned as the LLM reads it and is the format most layout-aware parsers (Unstructured, Docling) produce natively instead of flat text.
- **Per-row records** (for large tables that don't fit a chunk budget): when a table's full markdown rendering exceeds the chunk size, split by row — carrying the header row along with each row group (or each individual row, for very wide tables) so every chunk is independently interpretable without needing the rest of the table for context. Track row index and any primary key as chunk metadata so results can be re-assembled or deduplicated downstream.
- **Summary + reference** (for very large or very wide tables where even per-row chunking produces too many nearly-identical, low-signal chunks): generate a natural-language summary of the table's contents and structure as the retrievable unit, with a pointer/reference to the full table stored separately for the generation step to pull in on demand — trading some retrieval precision on individual cell values for a chunk that's actually meaningful as a similarity-search target.

### PDFs: multi-column, headers/footers, OCR fallback, and the silent interleaving failure

**The specific failure, named precisely.** PDF text extraction that ignores layout reads content in whatever order the PDF's internal object stream encodes, which for a two-column layout is frequently interleaved — a line from the left column, then a line from the right column, alternating — producing fluent, grammatically plausible but semantically scrambled text. This is a *silent* failure: no exception is thrown, no malformed output is visible at a glance, and it can survive all the way to a wrong answer that reads as confidently as a correct one, since the LLM has no way to know the sentence it's reading was assembled from two unrelated columns.

**Layout-aware extraction is the fix, with real tool variance.** Modern parsers run a layout-detection pass (bounding boxes for text blocks, tables, headers, footers, columns) before extracting text, so extraction follows visual reading order rather than byte order. This is not a solved problem uniformly across tools: LlamaParse's higher-throughput "accurate" mode has a documented reading-order weakness specifically on multi-column layouts, while Docling and Marker-PDF are more commonly recommended for documents (academic papers, dense reports) where getting multi-column order exactly right matters most — the practical takeaway is to validate a candidate parser against your own corpus's actual layout complexity rather than assuming any single tool handles every layout equally well.

**Headers and footers** (page numbers, running titles, boilerplate legal text repeated on every page) should be detected and stripped or handled as their own category, not chunked as if they were body content — a page footer repeated identically across 200 pages otherwise pollutes the corpus with 200 near-duplicate low-information chunks.

**OCR fallback.** Born-digital PDFs (text is a real, selectable text layer) extract directly; scanned PDFs (the page is an image with no text layer) extract nothing at all from a text-only pipeline and need OCR (EasyOCR, Tesseract) triggered specifically for pages where text-layer extraction returns near-empty content — a text-extraction pipeline with no OCR fallback doesn't fail loudly on a scanned page, it just silently returns an empty or near-empty chunk for that entire page.

### Code: AST-aware splitting, and why it must be tree-based, not line-based

Character- or line-count splitting on code routinely cuts a function mid-body, separating a signature from its implementation, or discards the enclosing class/import context a retrieved fragment needs to make sense on its own — this is the code-specific version of the chunking-boundary failure covered generally in `01-chunking`, but code has a stricter failure mode because a partial function is not just less useful, it's frequently unusable for the downstream task (code generation, code review) that retrieved it.

The fix is parsing the code into an abstract syntax tree (via `tree-sitter`, which has grammars for essentially every mainstream language) and walking the tree to identify logical units — functions, methods, classes — as the natural chunk boundaries, splitting further only at the finest available AST boundary (nested blocks, statements) when a single function still exceeds the chunk budget. This guarantees every chunk (barring the oversized-function edge case) is syntactically complete on its own, which a character-count split can never guarantee regardless of how the count is tuned. Recent work (cAST, arXiv:2506.15655) formalizes this as a measurable retrieval-quality improvement over naive line-based splitting for code-RAG tasks specifically, not just an intuitive best practice.

### Hierarchical documents and parent-child retrieval

Long, internally cross-referential documents (policy manuals, RFCs, technical standards, large contracts) have the same tension `01-chunking` describes generically — small chunks lose surrounding context, large chunks over-compress — but at a scale where neither a single small nor a single large chunk size serves the whole document well, because different sections have genuinely different natural granularity (a short definition versus a dense, multi-page procedural section).

The fix is a chunk *hierarchy* rather than one flat size: parse the document into nested parent-child structure (e.g. section → subsection → paragraph), index the small leaf-level chunks for embedding similarity search (since fine-grained chunks retrieve more precisely), but retrieve the parent chunk instead of the raw leaves when enough of a parent's children are retrieved together for the same query — LlamaIndex's `AutoMergingRetriever` implements exactly this pattern. The result: retrieval precision from small chunks, context completeness from the parent substitution, without having to guess one universal chunk size for a document whose sections vary widely in natural density.

### Images and figure captions

No text embedding model can see pixels: an image or figure embedded in a source document is invisible to the retrieval pipeline unless something turns it into text first. The standard mitigation is a captioning step — a vision-capable model generates a text description of the image (or of a chart's data and axes, or a diagram's structure) at ingest time, and that caption becomes the retrievable unit, typically with the source image stored as a reference for the generation step to include directly in its final answer rather than relying on the caption alone to convey everything. This is a lossy compression of the image's actual information content into text, so caption quality directly bounds what queries about that image can succeed — a caption that only says "a chart showing quarterly data" gives the retrieval pipeline nothing to match a specific "what was Q3 revenue" query against.

### Entity extraction into a knowledge graph, and when it pays

Flat chunk-based retrieval answers "which passages are similar to this query" well, but structurally cannot answer questions that require connecting facts scattered across many documents — "which vendors does our largest customer's parent company also do business with" requires traversing relationships, not just finding topically similar text. Knowledge-graph-augmented RAG (GraphRAG and its descendants) extracts entities and relationships from the corpus at ingest time into an explicit graph, then answers multi-hop or "global" (whole-corpus-summary) queries by traversing that graph and/or reading pre-computed community summaries, rather than relying on a similarity search that has no notion of relationship structure at all.

**The honest cost profile, with real numbers.** Microsoft's own published analysis found entity/relationship extraction (few-shot LLM prompting over every chunk) inflating token usage roughly 3-5x over plain chunking, with early GraphRAG indexing runs costing on the order of tens of thousands of dollars for a large corpus (one widely-cited figure: around $33,000 to index a single dataset in early 2024) and adding a measured 2-3x higher end-to-end query latency from graph traversal and community-summary generation at query time — this is a real, cited operational cost, not a hypothetical one. Cost has been dropping fast since: Microsoft reports indexing cost falling to roughly 0.1% of that original figure within about 18 months through better extraction prompting and caching, and lighter-weight approaches — LightRAG (~60% lower indexing token cost, close to half the median query latency of naive GraphRAG) and KET-RAG (limiting expensive LLM-based extraction to a PageRank-selected subset of chunks, combined with a cheap keyword-bipartite graph for the rest) — trade some graph completeness for a meaningfully cheaper pipeline.

**When it pays off, concretely:** multi-hop reasoning queries, "global" questions that need a whole-corpus synthesis no single retrieved chunk could ever answer, and domains with genuinely rich, queryable entity relationships (org structures, supply chains, regulatory relationships) where the value of answering relationship-shaped questions correctly outweighs the indexing cost and query-latency tax. It does not pay off as a blanket upgrade to plain RAG for corpora and query patterns that are fundamentally "find the passage that answers this" rather than "connect facts across passages" — that's exactly what flat chunking plus a good reranker (`05-reranking`) already does well and far more cheaply.

### Provenance metadata

Every structured unit produced by this stage — a table chunk, a captioned image, a graph entity — should carry provenance metadata back to its source (document ID, page/section, extraction method, extraction confidence where available) as a first-class field, not an afterthought. This is what makes the failure modes in this module diagnosable at all: without provenance, a wrong answer traced back to a scrambled multi-column extraction or a bad OCR read looks identical to any other retrieval failure, and the error-analysis loop (`13-accuracy-tuning`) has nothing to classify against.

### Decision table by source type

| Source type | Primary risk if naively chunked | Recommended approach |
|---|---|---|
| Tables (small-medium) | Row/column alignment destroyed, diluted embedding | Markdown serialization with repeated header row |
| Tables (large) | Same, plus exceeds chunk budget | Per-row records, header carried with each row group, row index as metadata |
| Tables (very large/wide) | Per-row chunking produces excessive near-duplicate low-signal chunks | Summary + reference to full table stored separately |
| PDF, single-column, born-digital | Low risk with any reasonable extractor | Standard layout-aware extraction (Unstructured/Docling) |
| PDF, multi-column | Reading order interleaved across columns, silent failure | Layout-aware parser validated on your corpus (Docling/Marker-PDF for complex layouts; verify LlamaParse's accurate-mode reading order specifically) |
| PDF, scanned (no text layer) | Zero extractable text, silently empty chunks | OCR fallback (EasyOCR/Tesseract) triggered by text-density detection |
| Code | Function split mid-body, missing enclosing context | AST-aware split via tree-sitter at function/class boundaries |
| Long/hierarchical docs | One flat chunk size wrong for every section | Parent-child hierarchy + retrieval-time merging (auto-merging retriever) |
| Images/figures/charts | Invisible to text embeddings entirely | Vision-model captioning; store image as reference, caption as retrievable text |
| Highly relational, multi-hop queries | Flat chunks can't connect facts across documents | Knowledge graph extraction (GraphRAG-style), only if query pattern justifies the cost |

---

## Build it from scratch

```python
# untested sketch — illustrates the source-type dispatch and the mechanics of
# per-row table chunking and AST-boundary code splitting, not production code
from dataclasses import dataclass, field


@dataclass
class Chunk:
    text: str
    metadata: dict = field(default_factory=dict)  # provenance: source_id, page, method, etc.


def table_to_markdown_chunks(headers: list[str], rows: list[list[str]], max_rows_per_chunk: int = 20, source_id: str = "") -> list[Chunk]:
    """Per-row fallback when the full table doesn't fit one chunk budget."""
    chunks = []
    for i in range(0, len(rows), max_rows_per_chunk):
        batch = rows[i:i + max_rows_per_chunk]
        header_line = "| " + " | ".join(headers) + " |"
        sep_line = "| " + " | ".join("---" for _ in headers) + " |"
        row_lines = ["| " + " | ".join(r) + " |" for r in batch]
        md = "\n".join([header_line, sep_line, *row_lines])
        chunks.append(Chunk(text=md, metadata={"source_id": source_id, "row_start": i, "row_end": i + len(batch)}))
    return chunks


def split_code_by_ast(source: str, ast_nodes: list[dict], max_chunk_size: int, source_id: str = "") -> list[Chunk]:
    """ast_nodes: [{'type': 'function'|'class', 'start': int, 'end': int, 'name': str}, ...]
    from a tree-sitter walk, in source order. Falls back to a raw slice only
    when a single node still exceeds max_chunk_size (real systems recurse
    into nested AST boundaries here instead)."""
    chunks = []
    for node in ast_nodes:
        text = source[node["start"]:node["end"]]
        if len(text) <= max_chunk_size:
            chunks.append(Chunk(text=text, metadata={"source_id": source_id, "symbol": node["name"], "type": node["type"]}))
        else:
            # real implementation recurses into nested blocks/statements here
            chunks.append(Chunk(text=text[:max_chunk_size], metadata={"source_id": source_id, "symbol": node["name"], "truncated": True}))
    return chunks


def dispatch_by_source_type(doc: dict) -> str:
    """doc: {'type': 'table'|'pdf_multicolumn'|'pdf_scanned'|'code'|'hierarchical'|'image', ...}
    Mechanical illustration of the decision table above -- routes to the
    right extraction/structuring path BEFORE 01-chunking ever runs."""
    routing = {
        "table": "markdown_serialize_or_per_row",
        "pdf_multicolumn": "layout_aware_parser_verify_reading_order",
        "pdf_scanned": "ocr_fallback",
        "code": "ast_aware_split",
        "hierarchical": "parent_child_index_with_automerge",
        "image": "vision_caption_then_embed_caption",
    }
    return routing.get(doc["type"], "standard_text_chunking")
```

---

## How it's done in production

**Layout-aware parsing**: Unstructured (open-source + API, general-purpose, ML layout detection), Docling (open-source, strong multi-column and academic-paper handling), LlamaParse (vision-based, convenient API, documented reading-order weakness on complex multi-column layouts in accurate mode), Marker-PDF (open-source, competitive on complex layouts). **OCR**: EasyOCR, Tesseract, triggered by text-density detection on a per-page basis. **Code chunking**: tree-sitter-based splitters (e.g. `code-chunk`, `slabs`/CodeChunker) for AST-boundary-aware splitting across mainstream languages. **Hierarchical retrieval**: LlamaIndex's hierarchical node parser plus `AutoMergingRetriever`. **Knowledge graphs**: Microsoft GraphRAG (reference implementation), LightRAG and KET-RAG (cost-reduced variants). **Image captioning**: any vision-capable multimodal model run at ingest time, with captions embedded and source images stored for retrieval-time inclusion.

| Symptom | Cause | Fix |
|---|---|---|
| Retrieved chunk reads fluently but answers a subtly wrong or nonsensical question | Multi-column PDF text interleaved during extraction — a silent reading-order failure, not a chunking problem | Switch to or validate a layout-aware parser's multi-column handling specifically (Docling/Marker-PDF); spot-check extracted text against the source PDF's visual layout |
| Table-derived answers cite the wrong number for a given row/column | Table flattened to plain text at extraction, destroying alignment | Serialize tables to markdown (or per-row records for large tables) instead of flat text; verify the parser is doing this by default |
| A scanned document contributes zero retrievable content | No OCR fallback — text-layer extraction silently returns empty on image-only pages | Add OCR (EasyOCR/Tesseract) triggered by low text-density detection per page |
| Code search returns half a function or a function with no import/class context | Character- or line-count splitting instead of AST-aware boundaries | Use a tree-sitter-based splitter at function/class boundaries |
| A user's question about a specific policy subsection returns either too little context or an irrelevantly huge chunk | Single flat chunk size wrong for a document whose sections vary widely in natural density | Hierarchical parent-child chunking with retrieval-time merging (auto-merging retriever) |
| Queries about a chart or diagram in the source document never retrieve anything relevant | Image/figure has no text representation at all | Add a captioning step at ingest time; verify caption quality specifically, since a vague caption bounds what queries can succeed |
| A knowledge-graph-augmented pipeline ships and query latency roughly triples with no clear accuracy win on most queries | GraphRAG applied to a query pattern that's mostly single-hop lookup, not multi-hop/relational | Profile actual query patterns before adopting a graph; fall back to flat chunking + reranking for the majority single-hop case, reserve the graph path for genuinely multi-hop queries |

---

## Tradeoffs & when NOT to use it

- **Don't default to a knowledge graph because a corpus "seems complex."** The 2-3x query-latency tax and (even after recent cost reductions) real indexing overhead only pay off for genuinely multi-hop or whole-corpus-summary query patterns; profile actual queries first, since most production RAG traffic is single-hop lookup that flat chunking plus reranking already serves well and far more cheaply.
- **Don't trust a single PDF parser across every document layout in your corpus.** LlamaParse's accurate mode, Docling, and Marker-PDF have measurably different strengths on multi-column and complex-layout documents; validate against a representative sample of your actual corpus rather than picking one tool once and assuming it generalizes.
- **Don't caption every image at maximum verbosity by default.** A caption is a lossy compression of the image into text, and an overly generic caption ("a chart showing data") is retrievally useless while an overly long one dilutes the embedding the same way an over-large text chunk does (`01-chunking`) — caption granularity is its own tuning problem, not a solved default.
- **Don't build a full parent-child hierarchy for short, structurally flat documents.** FAQ entries, short support tickets, and single-topic articles gain nothing from hierarchical retrieval machinery and pay unnecessary indexing/retrieval complexity for it — reserve this for documents where sections genuinely differ in natural density.
- **Don't skip provenance metadata to save ingest-time engineering effort.** Without it, every failure traced to a bad extraction (scrambled columns, a bad OCR read, a truncated table) looks identical to a generic retrieval failure, and the error-analysis loop (`13-accuracy-tuning`) has no way to isolate this pipeline stage from any other.

---

## Interview questions

### Q1 — Why does a naive PDF text extractor fail on a two-column layout, and why is the failure dangerous specifically because it's silent?
**Testing:** baseline understanding of the reading-order problem.
**Answer:** Text extraction that ignores layout reads content in the PDF's internal object order, which for two columns is frequently interleaved line-by-line across columns rather than reading each column fully before the next. The result is fluent, grammatically plausible text that is semantically scrambled — no exception is thrown, nothing looks obviously broken, and it can survive all the way to a confidently wrong answer.
**Follow-up trap:** *"Wouldn't a human proofreading a sample catch this?"* — only if they specifically compare extracted text against the source PDF's visual layout; skimming extracted text alone often reads plausibly enough that the interleaving isn't obvious without that comparison.

### Q2 — Compare markdown serialization, per-row records, and summary+reference as table-handling strategies. When would you pick each?
**Answer:** Markdown serialization (default for small-medium tables) keeps columns aligned in a format the LLM reads naturally. Per-row records are the fallback when a table's full markdown exceeds the chunk budget — split by row, carrying the header along, tracking row index as metadata. Summary+reference is for very large/wide tables where even per-row chunking produces too many near-duplicate low-signal chunks — summarize for retrieval, keep the full table as a reference the generation step pulls in directly.
**Follow-up trap:** *"Isn't markdown serialization always sufficient if you just make the chunk size big enough?"* — no, an oversized chunk to fit a huge table reintroduces the over-compression failure from `01-chunking`; table size should drive which of the three strategies you pick, not just chunk-size inflation.

### Q3 — Why must code be split on AST boundaries instead of character or line counts?
**Answer:** Character/line splitting routinely cuts a function mid-body or discards its enclosing class/import context, and a partial function is frequently unusable for the downstream task (code generation, review) that retrieved it — a stricter failure than a partial paragraph in prose. AST-aware splitting (via tree-sitter) guarantees chunks are syntactically complete units (functions, classes) except for the rare oversized-function case, which real implementations handle by recursing into nested AST boundaries rather than falling back to a raw character cut.
**Follow-up trap:** *"What do you do when a single function is too large for the chunk budget even after AST splitting?"* — recurse into the function's own nested blocks/statements as the next-finest AST boundary, rather than reverting to an arbitrary character cut, which would reintroduce the exact failure AST-awareness exists to prevent.

### Q4 — What is parent-child hierarchical retrieval, and what specific problem does it solve that a single flat chunk size can't?
**Answer:** It indexes small leaf chunks for precise embedding similarity search, but substitutes the parent chunk at retrieval time when enough of that parent's children are retrieved together for the same query (LlamaIndex's `AutoMergingRetriever` implements this). It solves the case where a document's sections vary widely in natural density — a short definition and a dense multi-page procedure can't both be served well by one universal chunk size, but a hierarchy lets each section's natural granularity coexist.
**Follow-up trap:** *"Isn't this just chunking at two different sizes and picking one?"* — no, the retrieval-time merging is the key mechanism: it decides per-query, based on how many children were actually retrieved together, rather than committing to one size or the other for the whole document upfront.

### Q5 — Why is a captioned image a lossy representation, and what's the practical consequence?
**Answer:** A caption compresses the image's full information content into text, so retrieval can only succeed for queries the caption's text actually captures — a vague caption ("a chart showing data") gives the retrieval pipeline nothing to match a specific query ("what was Q3 revenue") against, even though the answer is literally visible in the image.
**Follow-up trap:** *"So should captions always be as detailed as possible?"* — no, an overly long, overly generic-detail caption dilutes the embedding the same way an oversized text chunk does; caption granularity needs its own tuning against expected query types, not a maximalist default.

### Q6 — What is knowledge-graph-augmented RAG actually good at that flat chunk retrieval structurally cannot do?
**Answer:** Multi-hop questions that require connecting facts scattered across many documents ("which vendors does our largest customer's parent company also do business with") and "global" whole-corpus-summary questions that no single retrieved chunk could ever answer on its own, because similarity search has no notion of relationship structure between entities across documents.
**Follow-up trap:** *"Doesn't a good reranker with a large enough k solve multi-hop questions too?"* — no, reranking still only reorders individually retrieved passages; it doesn't synthesize a chain of relationships across documents the way an explicit graph traversal can, so a bigger k or a better reranker doesn't substitute for genuine relational structure.

### Q7 — Give the real cost profile of knowledge-graph RAG, with numbers, and explain what's driven recent cost reduction.
**Answer:** Entity/relationship extraction inflates token usage roughly 3-5x over plain chunking, early indexing runs for a large corpus were reported around $33,000, and query-time graph traversal/community summarization adds a measured 2-3x higher end-to-end latency versus flat retrieval. Cost has since dropped fast — Microsoft reports indexing cost falling to roughly 0.1% of that original figure within about 18 months via better extraction prompting and caching, and lighter approaches (LightRAG: ~60% lower indexing token cost, near-half the query latency; KET-RAG: LLM extraction limited to a PageRank-selected subset of chunks) trade some graph completeness for much lower cost.
**Follow-up trap:** *"So is GraphRAG now cheap enough to use by default?"* — indexing cost has dropped sharply, but the query-time latency tax hasn't fallen as fast and remains a real constraint; the honest answer is that cost is no longer the primary blocker for many corpora, but query pattern (does the workload actually need multi-hop/global reasoning) still is.

### Q8 — Why do headers and footers need special handling rather than being chunked like body text?
**Answer:** Page headers/footers (running titles, page numbers, repeated boilerplate) appear identically or near-identically on every page; chunking them as body content pollutes the corpus with dozens or hundreds of near-duplicate, low-information chunks that compete for top-k slots against genuinely useful content.
**Follow-up trap:** *"Could you just filter them out entirely rather than handling them specially?"* — usually yes for pure boilerplate, but some "footer-like" content (a section reference number, a document ID relevant to provenance) has legitimate metadata value even if it shouldn't be chunked as retrievable text — the right handling is often "extract as metadata, don't chunk as content," not blanket deletion.

### Q9 — A team ships a PDF ingestion pipeline that works well on their test set of single-column reports, then silently degrades in accuracy once real customer documents (multi-column financial statements with embedded tables) start flowing in. Diagnose.
**Answer:** The test set almost certainly didn't include multi-column or table-heavy layouts, so the parser's reading-order and table-flattening behavior was never exercised — this is the data-structuring equivalent of the eval-distribution-mismatch failure in `13-accuracy-tuning`. Diagnose by comparing extracted text against source-document visual layout on a sample of the actual failing documents, not by re-running the existing eval, since the existing eval structurally can't surface this class of bug.
**Follow-up trap:** *"Wouldn't recall@k eval numbers have caught this?"* — only if the golden set includes queries against multi-column/table-heavy documents specifically; a golden set built before those document types existed in the corpus is exactly the kind of stale, non-representative eval this module and `13-accuracy-tuning` both warn against.

### Q10 — When is it wrong to build a full parent-child hierarchy or a knowledge graph, even though both are "more sophisticated" than flat chunking?
**Answer:** Parent-child hierarchies are wasted complexity on short, structurally flat documents (FAQ entries, tickets) that don't have meaningfully different section densities to exploit. Knowledge graphs are wasted cost and latency on corpora and query patterns that are fundamentally single-hop lookup rather than multi-hop/relational — in both cases the "more sophisticated" technique adds real engineering and runtime cost without a query pattern that needs what it specifically provides.
**Follow-up trap:** *"How would you decide, concretely, before building either?"* — profile actual or expected query patterns first (what fraction are multi-hop vs. single-hop; does document structure genuinely vary in density across sections) rather than defaulting to the more sophisticated technique because it's available.

### Q11 — Design the ingestion pipeline for a corpus that mixes scanned invoices, a multi-column technical report, a codebase, and a 300-page policy manual.
**Testing:** synthesis across the whole decision table.
**Answer:** Route by detected source type before any chunking: scanned invoices get OCR fallback triggered by per-page text-density detection, with extracted line items serialized as per-row table records (small documents, so markdown/per-row is sufficient, no need for summary+reference). The multi-column technical report goes through a layout-aware parser validated specifically for multi-column reading order (Docling/Marker-PDF over a parser with known multi-column weaknesses), with any embedded tables serialized to markdown. The codebase is split via tree-sitter at function/class AST boundaries, never by character count. The 300-page policy manual uses hierarchical parent-child chunking with retrieval-time auto-merging, since its sections vary widely in natural density (short definitions next to dense procedural sections) and cross-references make a single flat chunk size actively wrong. Every unit produced by all four paths carries provenance metadata (source type, extraction method, document/page/section ID) so downstream error analysis (`13-accuracy-tuning`) can isolate ingestion-stage failures from retrieval or generation failures.
**Follow-up trap:** *"Would you build a knowledge graph across all four sources given how relationally connected invoices, reports, and policies often are in practice?"* — only if the actual query pattern requires multi-hop reasoning across those sources (e.g. "which invoices reference a vendor mentioned in this policy exception"); if most real queries are single-source lookups, the graph's cost and latency tax isn't justified regardless of how relationally connected the underlying data theoretically is.

---

## Red flags that fail you

- Treating PDF text extraction as a solved, uniform problem across every parser and layout.
- Not knowing that multi-column PDF extraction can silently interleave columns with no visible error.
- Flattening tables to plain text and calling it "extracted."
- Splitting code by character or line count instead of AST boundaries.
- Assuming a single flat chunk size serves every section of a long, heterogeneous document equally well.
- Believing an image is "handled" by RAG without a captioning step.
- Recommending a knowledge graph without naming the specific multi-hop/global query pattern that justifies its cost and latency tax.
- Skipping provenance metadata and having no way to diagnose which pipeline stage produced a bad answer.

---

## Cheat card

```
BEFORE-CHUNKING PRINCIPLE   chunking strategy is downstream of extraction --
   bad structure in = no chunk-size tuning fixes it.

TABLES   small/medium -> markdown serialize (repeat header row).
         large -> per-row records, header carried per group, row index as metadata.
         very large/wide -> summary + reference to full table stored separately.

PDFs   multi-column -> reading order can silently interleave columns (no error
       thrown). LlamaParse accurate-mode has a documented weakness here;
       Docling/Marker-PDF more reliable on complex multi-column layouts --
       VALIDATE against your own corpus, don't assume one tool generalizes.
       scanned (no text layer) -> OCR fallback (EasyOCR/Tesseract) triggered
       by per-page text-density detection.
       headers/footers -> extract as metadata or strip, never chunk as body text.

CODE   AST-aware split via tree-sitter at function/class boundaries, NEVER
       character/line count. Oversized function -> recurse into nested AST
       boundaries, don't fall back to a raw cut. (cAST, arXiv:2506.15655)

HIERARCHICAL DOCS   parent-child chunking + retrieval-time merge (LlamaIndex
       AutoMergingRetriever): index small leaf chunks for precision, promote
       to parent chunk when enough children retrieved together. Fixes
       "sections vary wildly in natural density" that one flat size can't.

IMAGES   invisible to text embeddings without a captioning step (vision
       model at ingest time). Caption = lossy compression -> caption quality
       directly bounds which queries about that image can succeed.

KNOWLEDGE GRAPHS   pays off ONLY for multi-hop / global-summary query
       patterns flat chunks structurally can't answer.
       Cost (real numbers): entity extraction ~3-5x token inflation over
       plain chunking; early indexing ~$33k for a large corpus (2024);
       query latency 2-3x higher (graph traversal + community summaries).
       Dropped fast since: MSFT reports ~0.1% of original indexing cost
       within ~18mo. LightRAG: ~60% less indexing cost, ~half query latency.
       KET-RAG: LLM extraction limited to PageRank-selected core chunks.

PROVENANCE   every chunk/caption/entity needs source_id, page/section,
       extraction method as metadata -- without it, ingestion-stage failures
       are indistinguishable from retrieval/generation failures downstream.
```

## Sources

- [Our Approach to Table Chunking — Ragie](https://www.ragie.ai/blog/our-approach-to-table-chunking) — accessed 2026-08-01
- [Best AI PDF Parsers for 2026 — LlamaIndex](https://www.llamaindex.ai/insights/best-ai-pdf-parsers) — accessed 2026-08-01
- [What Is Multi-Column Document Parsing? — LlamaIndex Glossary](https://www.llamaindex.ai/glossary/multi-column-document-parsing) — accessed 2026-08-01
- [Best PDF Parsers for AI and RAG Workflows in 2026 — Firecrawl](https://www.firecrawl.dev/blog/best-pdf-parsers) — accessed 2026-08-01
- [cAST: Enhancing Code Retrieval-Augmented Generation with Structural Chunking via Abstract Syntax Tree (arXiv:2506.15655)](https://arxiv.org/pdf/2506.15655) — accessed 2026-08-01
- [Auto Merging Retriever — LlamaIndex Documentation](https://docs.llamaindex.ai/en/v0.10.17/examples/retrievers/auto_merging_retriever.html) — accessed 2026-08-01
- [The GraphRAG Cost Cliff: How $33,000 Became $33 in Eighteen Months — Graph Praxis](https://medium.com/graph-praxis/the-graphrag-cost-cliff-how-33-000-became-33-in-eighteen-months-be1b0fbe37e4) — accessed 2026-08-01
- [Microsoft Releases GraphRAG 2.0 with Enhanced Knowledge Graph Integration — Ailog RAG](https://app.ailog.fr/en/blog/news/graphrag-2-microsoft) — accessed 2026-08-01

## Changelog
- 2026-08-01 — created
