# How production does it

## Hugging Face tokenizers — Rust is where tokenizers live

The `tokenizers` crate (behind Python's `transformers`) implements your exact
pipeline, industrialised:

- **Training is a priority queue, not rescans.** Your `train` recount pairs
  every iteration — O(iterations × corpus). Production keeps pair counts in a
  heap keyed by `(count, pair)` and updates only neighbours of each merge
  position. Same output (with the same lowest-pair tie-break), orders faster.
- **Parallel counting with Rayon.** Word counts shard across threads; merges
  stay sequential and deterministic.
- **The pre-tokeniser is load-bearing.** GPT-2's regex splits text into words
  BEFORE BPE so merges never cross whitespace/word boundaries — that's why
  "skyscraper" and "sky scraper" tokenize differently despite identical bytes.
- **Byte-level mapping trick.** Instead of raw bytes, printable unicode glyphs
  map to bytes (the `bytes_to_unicode` table) so vocab files are inspectable
  text. Same ids underneath.

## tiktoken (OpenAI)

Same BPE core, tuned differently: precompiled merge ranks as flat arrays,
regex pre-tokenisation in Rust with memory-mapped patterns, and an explicit
`decode` that substitutes U+FFFD rather than erroring on partial sequences —
a production judgement call your strict `InvalidUtf8` deliberately rejects.

## What the interview probe looks for

- "Why byte-level?" (No `<UNK>`, ever — every string round-trips.)
- "What does the tie-break change?" (Determinism and which tokens exist at
  all when frequencies collide — different corpora, different vocab shapes.)
- "Where is the time actually spent?" (Pair counting → heap + incremental updates.)
- "Why do merges apply by rank, not greedily left-to-right?" (Earliest-learned
  merge reproduces training-time composition; greedy gives different ids.)
