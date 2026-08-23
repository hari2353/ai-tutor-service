# Lab 01 (Rust): A Byte-Level BPE Tokenizer

**Track:** T05 LLM Internals · **Time:** 1.5h · **XP:** 50
**Module:** `T05-tokenization`

**You will build:** byte-level BPE from scratch — training, encoding,
decoding — in pure Rust with no dependencies, deterministic, and correct on
ASCII, unicode and emoji.

**You will be able to answer:** *"Why does byte-level BPE never produce an unknown token, and what exactly does a merge tie-break change?"*

## Setup

```bash
cd labs/rust/01-bpe-tokenizer
cargo --version        # any 1.7x+ — zero crates.io dependencies
```

## How starter/solution selection works

- Default build compiles `src/starter.rs` (`todo!()` stubs → the suite FAILS).
- `--features solution` compiles `src/solution.rs` instead.
- Same public API both ways; `lib.rs` does the compile-time switch.

```bash
cargo test                        # against starter → FAILS. Make them pass.
cargo test --features solution    # reference must pass
cargo clippy --all-targets        # stay clean
```

## The spec

1. **`train(text, vocab_size) -> Vec<Merge>`** — vocab starts as the 256 raw
   bytes (ids `0..=255`); each merge appends id `256 + merge_index`. Every
   iteration: count adjacent pairs in the current id sequence, merge the MOST
   FREQUENT one; **ties break to the LOWEST pair** (lexicographic tuple
   order). Return merges in creation order. Stop early when the corpus runs
   out of pairs.
2. **`encode(text, &merges) -> Vec<u32>`** — start from UTF-8 bytes;
   repeatedly apply the *earliest-learned* applicable merge (lowest rank
   wins — rank beats leftmost position!) until none applies. Un-merged text
   stays as raw bytes: there is no `<UNK>` in this world.
3. **`decode(&ids, &merges) -> Result<String, DecodeError>`** — rebuild the
   id→bytes table from the merges and join. `decode(encode(x)) == x` must
   hold for ASCII **and** non-ASCII (`café`, `日本語`, emoji incl. ZWJ
   sequences) because everything rides on UTF-8 bytes.
4. **Errors are clean** — an id outside `[0, 256+merges.len())` is
   `DecodeError::UnknownId(n)`; decoded bytes that aren't valid UTF-8 are
   `DecodeError::InvalidUtf8`. No panics on bad input.

## Run the tests

```bash
cargo test --features solution -- --nocapture
```

Two tests worth reading before you start:
`ties_break_to_the_lowest_pair` (scanning order must not decide merges) and
`encoding_applies_the_earliest_learned_merge_first` (rank beats position).

## Stretch goals

1. **Load/save** — serialise merges to a `.json` vocab file like GPT-2's and
   round-trip it. *(Interview: "what exactly is in a tokenizer.json?")*
2. **Special tokens** — reserve ids above the merges for `<|endoftext|>`,
   split around them in `encode`. *(Interview: "how do special tokens interact
   with BPE merges?")*
3. **Regex pre-tokenisation** — GPT-2 splits on a pattern before BPE so
   merges never cross word boundaries. Why does "skyscraper" vs "sky scraper" care?
4. **Compression curve** — plot bytes/token over vocab size for a real corpus.
   Where do returns flatten?
