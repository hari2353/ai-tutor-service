# Lab 03: A Byte-Level BPE Tokenizer

**Track:** T05 Tokenization · **Time:** 1.5h · **XP:** 50
**Module:** `T05-tokenization`

**You will build:** byte-level BPE from scratch — training, encoding, decoding — pure stdlib, deterministic, and correct on ASCII, unicode and emoji.

**You will be able to answer:** *"Why does byte-level BPE never produce an unknown token, and what exactly does a merge tie-break change?"*

## Setup

```bash
cd labs/py/03-bpe-tokenizer
python -m venv .venv && . .venv/bin/activate     # or: uv venv && . .venv/bin/activate
pip install pytest                                # only dependency
```

## The spec

1. **`train(text, vocab_size)`** — byte-level BPE. Vocab starts as the 256 raw bytes (ids `0..255`); each merge appends one new id (`256 + merge_index`). At every iteration count adjacent pairs in the current id sequence and merge the most frequent one; **ties break to the lowest pair** (tuple comparison on the two ids). Return the merges list: `[(left_id, right_id), ...]` in creation order. If the corpus runs out of pairs before `vocab_size`, stop early.
2. **`encode(text, merges)`** — start from UTF-8 bytes, then repeatedly apply the *earliest-learned* applicable merge (lowest rank wins) until none applies. Text containing pairs that were never merged simply stays as raw bytes — there is no `<UNK>` in this world.
3. **`decode(ids, merges)`** — rebuild id → bytes from the merges and join. `decode(encode(x)) == x` must hold for ASCII **and** for non-ASCII text (`é`, `中`) because everything rides on UTF-8 bytes.
4. **Errors are clean** — decoding an id outside the vocab raises `ValueError`; decoding bytes that don't form valid UTF-8 also surfaces as a `ValueError` subclass.

## Run the tests

```bash
pytest tests/ -v          # against starter/ → FAILS. Make them pass.
```

To check the reference: `pytest tests/ -v --solution`

## Stretch goals

1. **Load/save** — serialise merges to a `.json` vocab file like GPT-2's, round-trip it.
2. **Special tokens** — reserve ids above the merges for `<|endoftext|>`; make `encode` split around them.
3. **Regex pre-tokenisation** — GPT-2 splits on a pattern before BPE so merges never cross word boundaries. Why does "skyscraper" vs "sky scraper" care?
4. **Compression metric** — plot bytes/token over vocab size for a real corpus. Where do returns flatten?
