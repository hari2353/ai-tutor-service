# Lab 02: Byte-Pair Encoding From Scratch

**Track:** T05 LLM Internals · **Time:** 2h · **XP:** 50
**Module:** `T05-tokenization`

**You will build:** a byte-level BPE tokenizer — training (merge learning), encoding, exact-roundtrip decoding, the GPT-2 space-marking convention.

**You will be able to answer:** *"Why byte-level BPE? What does tiktoken do differently from SentencePiece, and why does tokenization cause the 'strawberry has how many r's' failure?"*

## Setup

```bash
cd labs/py/02-tokenization
pip install pytest
```

## The spec

1. **`BPETokenizer(vocab_size)`** — `train(corpus)`: start from the 256 byte tokens; repeatedly merge the most-frequent adjacent pair. Tie-break: lexicographically smallest pair. Merges stored in learned order with ranks.
2. **`encode(text)`** — convert to bytes; repeatedly apply the lowest-rank applicable merge anywhere in the token list (GPT-2 algorithm) until none applies; cap at vocab_size tokens.
3. **`decode(ids)`** — map ids back through merge table / byte table; must roundtrip ANY string exactly.
4. **Space convention** — GPT-2 style: a space before a word becomes part of the word's first token. The classic rendering maps 'Ġ' to the space-prefixed byte; implement the equivalent by operating on raw bytes directly (space byte 0x20 leads the token) — the visible test is that "hello world" and "helloworld" encode differently.
5. **`vocab_growth(corpus, sizes)`** — helper returning `[(size, merges_learned)]` sanity data.

## Run the tests

```bash
pytest tests/ -q          # against starter/ — FAILS. Make them pass.
```

Reference: `pytest tests/ -q --solution`

## Stretch goals

1. **Regex pre-tokenization** — split on the GPT-2 pattern before counting merges; how does the learned vocab change?
2. **Unigram (SentencePiece-style) trainer** — pick vocab by likelihood, not merges; compare vocab efficiency on the same corpus.
3. **A tokenizer error audit** — construct the "e" + "e" vs "ée" vs "é" cases and show which produce the same tokens.
