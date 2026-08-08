# Lab 03: Byte-Pair Encoding, End to End

**Track:** T05 LLM Internals · **Time:** 2h · **XP:** 50
**Module:** `T05-tokenization`

**You will build:** a byte-level BPE tokenizer -- train merges from a corpus, encode,
decode -- with a deterministic merge order and a byte-level fallback so no input can
ever fail to encode.

**You will be able to answer:** *"Implement BPE. Why does byte-level BPE never need
an `<UNK>` token, and how do you make training deterministic?"*

## Setup

```bash
cd labs/py/03-bpe-tokenizer
python -m venv .venv && . .venv/bin/activate     # or: uv venv && . .venv/bin/activate
pip install pytest                                # only dependency
```

## The spec

1. **`BPETokenizer.train(corpus, vocab_size)`** -- start from the 256 raw byte
   values as the base vocabulary (ids `0..255`), then repeatedly find the most
   frequent adjacent pair across the whole corpus (counted **with multiplicity**,
   not deduplicated per line) and merge it into a new token, until `vocab_size` is
   reached or the corpus runs out of mergeable pairs.
2. **Deterministic merge order** -- ties in frequency are broken by picking the
   lexicographically smallest pair. Training the same corpus twice must produce
   byte-for-byte identical `merges`.
3. **`encode(text)` / `decode(ids)`** -- encode applies learned merges in rank
   order (earliest-learned first) until no more apply; decode concatenates each
   id's byte sequence and decodes as UTF-8. `decode(encode(s)) == s` must hold for
   every input, including unicode and emoji.
4. **Byte-level fallback** -- because the base vocabulary is all 256 byte values,
   there is no out-of-vocabulary case. A byte sequence with no matching merge just
   passes through as individual byte tokens -- this is not a special code path, it's
   what naturally happens when the merge loop finds nothing to do.
5. **Vocab size respected** -- `vocab_size` is a ceiling, not a guarantee: a small
   or repetitive corpus can run out of pairs before reaching it, and that's correct
   behaviour, not a bug.

## Run the tests

```bash
pytest tests/ -v          # against starter/ → FAILS. Make them pass.
```

To check the reference: `pytest tests/ -v --solution`

## Stretch goals

1. **Regex pre-tokenization** -- split on GPT-2's pattern (word boundaries,
   whitespace prefixes) before running BPE, and see how it changes which merges
   get learned. *(Interview: "why does GPT-2's tokenizer treat ` the` and `the`
   differently?")*
2. **Special tokens** -- add `<|endoftext|>` and friends as always-atomic tokens
   that never get merged into or out of, and never split by the byte-level
   fallback.
3. **Vocabulary fairness** -- train on an English-only corpus vs. a mixed
   English/Hindi/Chinese corpus at the same `vocab_size`, and measure
   tokens-per-sentence for equivalent content in each language. Quantify the
   fairness gap the T05 module describes.
4. **Compression ratio** -- plot `len(encode(s)) / len(s.encode('utf-8'))` against
   `vocab_size` on a held-out sample, and find the point of diminishing returns.
