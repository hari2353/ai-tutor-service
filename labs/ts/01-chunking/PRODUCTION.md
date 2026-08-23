# How production does it

## LangChain text splitters / LlamaIndex node parsers

Your three chunkers exist there almost verbatim:

- `RecursiveCharacterTextSplitter` IS your `recursiveChunks`: same separator
  ladder (`["\n\n", "\n", " ", ""]`), same keep-separator-glued rule, same
  greedy packing. Production adds a `keepSeparator` toggle because some
  pipelines want separators dropped instead of glued.
- `SentenceTransformersTokenTextSplitter` / `SemanticChunker` move the unit
  from characters to tokens or to embedding-distance breakpoints between
  sentences — your `sentenceChunks` is the substrate both build on.
- Overlap in production exists for ONE reason: answers whose evidence straddles
  a boundary get retrieved anyway. It costs index size (~size/stride ×), which
  is why default overlaps are small fractions, not half-windows.

## What real systems add beyond this lab

- **Length in tokens, not chars** — every serious deployment swaps the length
  function (your stretch goal #1). Chars lie by ~4x across languages.
- **Structure-aware ladders** — Markdown/HTML/Code splitters prepend heading,
  tag, and AST boundaries so chunks never cross semantic sections.
- **Spans, not strings** — production node objects carry `(start, end)`
  offsets into the original doc so citations and re-ranking can point back.
- **Idempotent ingestion checks** — the coverage property you implemented is
  essentially what ingestion-time validators assert before embedding: if
  stitched chunks don't cover the document, the pipeline is silently broken.

## What the interview probe looks for

- "What does overlap buy, and what does it cost?" (Boundary recall vs index bloat.)
- "How would you prove your splitter loses nothing?" (Coverage property / exact
  reconstruction at zero overlap.)
- "Why recurse through separators instead of sliding windows?"
  (Semantic boundaries survive; retrieval quality per token goes up.)
- "When is a huge chunk fine?" (Reranking-first pipelines; parent-document retrieval.)
