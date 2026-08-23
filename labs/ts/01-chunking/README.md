# Lab 01 (TypeScript): Text Chunking From Scratch

**Track:** T06 RAG (Retrieval-Augmented Generation) · **Time:** 2h · **XP:** 50
**Module:** `T06-chunking`

**You will build:** the three chunkers every RAG pipeline is built on — fixed
windows with overlap, recursive separator-ladder splitting, and sentence
packing with sentence-overlap — plus the coverage property that proves none of
them silently drop characters. Zero npm dependencies; Node's built-in test runner.

**You will be able to answer:** *"Walk me through recursive character splitting — what does overlap actually buy you, and how do you prove a splitter loses nothing?"*

## Setup

```bash
cd labs/ts/01-chunking
node --version      # 22.19+ (native TypeScript type stripping) — nothing else
```

## How starter/solution selection works

- Default imports `src/starter.ts` (TODO stubs → the suite FAILS).
- `CHUNK_IMPL=solution` switches the import to `src/solution.ts`.
- `tests/impl.ts` is the only place that knows the difference.

```bash
npm test                                  # starter → FAILS. Make them pass.
$env:CHUNK_IMPL='solution'; npm test      # reference must pass (bash: export)
```

## The spec

1. **`fixedChunks(text, size, overlap)`** — hard character windows with stride
   `size - overlap`; final window truncated when lengths don't align, never a
   redundant duplicate. Throw `RangeError` on `overlap >= size` (zero stride =
   infinite loop), negative overlap, or `size < 1`. `[]` for empty text.
2. **`recursiveChunks(text, size, separators?, overlap?)`** — try separators
   top-down (`"\n\n"` → `"\n"` → `". "` → `" "`), recursing into a finer one
   wherever a piece still exceeds `size`. `""` (character) split is always the
   final fallback, so an unbreakable 95-char run gets split anyway. **Keep
   separators glued to the preceding piece**: with `overlap = 0` the chunks
   must concatenate back to the original text *exactly*. With `overlap > 0`,
   prefix later chunks with up to `overlap` characters of context, capped so
   no chunk ever exceeds `size`.
3. **`sentenceChunks(text, size, overlapSentences = 1)`** — sentence
   boundaries after ASCII `.!?…` and CJK `。！？` (no trailing space needed),
   pack whole sentences into chunks `<= size`, repeat the last
   `overlapSentences` sentences at the start of the next chunk. A single
   sentence longer than `size` is emitted alone — an honest boundary beats a
   dishonest cut.
4. **`assertNoLoss(chunks, text, scheme)`** — the coverage property:
   - `kind: "fixed"` → chunk i must start at `i·(size-overlap)` and the last
     chunk must end at `text.length`;
   - `kind: "recursive"` → chunks join back to the source exactly;
   - `kind: "sentence"` → every source sentence survives inside some chunk.
   Throws naming the first uncovered range otherwise.

## Run the tests

```bash
node --test --test-reporter tap tests/chunking.test.ts
```

## Stretch goals

1. **Token-true sizing** — inject a `lengthFn(s): number` so chunks measure in
   tokenizer tokens instead of chars. *(Interview: "why is character size a lie for BGE-class models?")*
2. **Markdown-aware ladder** — prepend `\n# `, `\n## `, ```` ``` ```` splits so
   a chunk never crosses a section boundary.
3. **Offset-preserving API** — return `{text, start, end}` spans so citations
   can point back into the source document.
4. **Late-chunking bridge** — mean-pool fake "token embeddings" per span;
   note how spans (not strings) are what late chunking actually consumes.
