# Lab 08: Text Chunking From Scratch

**Track:** T06 RAG (Retrieval-Augmented Generation) · **Time:** 2h · **XP:** 50
**Module:** `T06-chunking`

**You will build:** the three chunkers every RAG pipeline is built on — fixed windows with overlap, recursive separator-ladder splitting, and sentence packing with sentence-overlap — plus the coverage property that proves none of them silently drop characters.

**You will be able to answer:** *"Walk me through recursive character splitting — what does overlap actually buy you, and how do you prove a splitter loses nothing?"*

## Setup

```bash
cd labs/py/08-chunking
python -m venv .venv && . .venv/bin/activate     # or: uv venv && . .venv/bin/activate
pip install pytest                                # only dependency
```

## The spec

1. **`fixed_chunks(text, size, overlap)`** — hard character windows with stride `size - overlap`; last window truncated, never a redundant duplicate. Reject `overlap >= size` (zero stride = infinite loop) and `size < 1`. `[]` for empty text. *(The 5-line version in the module notes has an off-by-one tail bug on some lengths — your tests will catch it.)*
2. **`recursive_chunks(text, size, separators=DEFAULT_SEPARATORS, overlap=0)`** — try separators top-down (`"\n\n"` → `"\n"` → `". "` → `" "`), recursing into a finer one only where a piece still exceeds `size`. The `""` (character) separator is always appended as the final fallback, so a 95-char unbreakable token gets split anyway. Keep separators glued to the preceding piece: with `overlap=0` the chunks must concatenate back to the original text *exactly*. With `overlap > 0`, prefix later chunks with up to `overlap` characters of context, capped so no chunk ever exceeds `size`.
3. **`sentence_chunks(text, size, overlap_sentences=1)`** — regex sentence boundaries (ASCII `.!?…` + CJK `。！？`, which need no trailing space), pack whole sentences into chunks `<= size`, and repeat the last `overlap_sentences` sentences at the start of the next chunk. A single sentence longer than `size` is emitted alone — an honest boundary beats a dishonest cut.
4. **`assert_no_loss(chunks, text)`** — the coverage property: stitched back onto the source with overlaps collapsed, the chunks must cover every character index — head starts at 0, no gap between consecutive chunks, tail ends at `len(text)`. Raises `AssertionError` naming the first uncovered range.

## Run the tests

```bash
pytest tests/ -v          # against starter/ → FAILS. Make them pass.
```

To check the reference: `pytest tests/ -v --solution`

## Stretch goals

1. **Token-true sizing** — swap the character length function for a tokenizer count (`len(encoder.encode(s))`) via an injectable `length_fn`. *(Interview: "why is character size a lie for BGE-class models?")*
2. **Markdown-aware separators** — prepend heading splits (`\n# `, `\n## `, ```\n```) to the ladder so a chunk never crosses a section boundary.
3. **Offset-preserving API** — return `(start, end)` spans alongside strings so citations can point back into the source document.
4. **Late-chunking bridge** — take the span list and mean-pool fake "token embeddings" per span; note how spans (not strings) are what late chunking actually needs.
