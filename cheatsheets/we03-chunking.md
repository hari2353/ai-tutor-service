# Chunking: Fixed, Recursive, Semantic, Contextual, Late

> Sprint weekend 3 · source: `curriculum/06-rag/01-chunking.md`

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
