# Production notes -- tokenization

## What you'd actually use

| Concern | This lab | Production |
|---|---|---|
| Training | Pure Python, O(corpus × merges) | `tiktoken` (Rust core) or `sentencepiece` (C++) -- orders of magnitude faster |
| Encoding | Re-scans the sequence every merge iteration | Precomputed regex pre-tokenization + a trie/priority-queue merge scan |
| Vocabulary | Ad hoc, whatever the corpus produces | Fixed, versioned, shipped with the model -- `cl100k_base`, `o200k_base`, etc. |
| Special tokens | None | `<|endoftext|>`, role markers, tool-call delimiters -- reserved ids, never touched by merges |
| Multilingual fairness | Not addressed | An open, actively-measured problem (see below) |

## What the real ones add over yours

- **Regex pre-tokenization before BPE runs at all.** GPT-2 onward splits text into
  chunks (roughly: contiguous letters, contiguous digits, one punctuation run, and
  whitespace handling that keeps a leading space attached to the following word)
  *before* BPE ever sees it. This is why "`the`" and "` the`" (with a leading space)
  are different tokens, and why numbers are chunked in ways that look arbitrary
  until you know the regex. This lab skips pre-tokenization entirely and runs BPE
  over the raw byte stream, which is simpler to implement and reason about but
  produces a different (still valid) vocabulary than a real GPT tokenizer.
- **A precomputed merge trie, not a rescan-from-scratch loop.** `tok.encode()` here
  recomputes the set of adjacent pairs from scratch every iteration -- fine for a
  lab, `O(n²)` in the worst case for long inputs. Production tokenizers pack the
  merge ranks into a structure that finds the next merge in closer to
  `O(n log n)` or better.
- **A fixed, versioned vocabulary shipped with the model.** You never train BPE at
  inference time in production -- the vocabulary is frozen the moment the model is
  trained, because token id `9906` meaning "Hello" is baked into the embedding
  table. Retraining the tokenizer without retraining the model is not a thing.
- **Special/reserved tokens.** `<|endoftext|>`, chat role markers, and tool-call
  delimiters get IDs that BPE is explicitly forbidden from ever producing or
  merging through -- a naive byte-level BPE could otherwise "discover" a merge that
  collides with a reserved sequence.

## What breaks at scale

| Symptom | Cause | Fix |
|---|---|---|
| Training takes hours on a large corpus | Naive O(corpus × merges) rescan, like this lab | Incremental pair-count updates (only recompute counts touched by the last merge), or a C/Rust implementation |
| Non-English users pay 2-5x more per request | Vocabulary trained predominantly on English/Latin-script web text | Train (or use) a vocabulary balanced across target languages; document the cost difference explicitly in pricing |
| A user's exact input round-trips to something subtly different | Text normalization applied before tokenization (NFC/NFKC) without the same normalization on decode | Either normalize consistently on both sides, or don't normalize at all (byte-level BPE as in this lab doesn't need to) |
| Token counts used for billing/rate-limiting drift from the model's actual count | Estimating with a different tokenizer than the one the model was trained with | Always count with the exact tokenizer + vocabulary version the model uses |
| A "poisoned" input causes a tokenizer-level exploit (adversarial tokens) | Vocabulary contains rare merges seen very few times during training that produce unexpected behaviour when reproduced adversarially | Documented issue with some released vocabularies (e.g. "SolidGoldMagikarp"-style glitch tokens); requires vocabulary auditing, not a tokenizer-algorithm fix |

## Cost & latency

Tokenization itself is cheap (microseconds per request with a compiled
implementation) but its output is the literal unit every LLM API bills and
rate-limits on. A vocabulary that's 20% less efficient for your traffic mix is a
20% cost tax with no model change required to fix it -- which is why vocabulary
size and multilingual balance are pricing decisions, not just engineering ones.

## The 3 questions an interviewer asks after you describe this

1. *"Your BPE has no pre-tokenization step. What breaks if you add it?"* -- merges
   can no longer cross whitespace/punctuation boundaries, which changes which pairs
   are even eligible, and usually improves compression on real text because it
   stops BPE from learning junk merges that happen to span word boundaries in a
   repetitive corpus.
2. *"You trained a fresh vocabulary. Why can't you swap it into a deployed model?"*
   -- the model's embedding table is indexed by token id; changing the vocabulary
   changes what id 500 means, which is equivalent to randomizing every embedding
   the model learned. The vocabulary is part of the model's weights, not a
   pluggable component.
3. *"How would you measure whether your tokenizer is unfair across languages?"* --
   fix a set of semantically equivalent sentences translated into each target
   language, tokenize all of them with the same vocabulary, and compare
   tokens-per-sentence (or tokens-per-character, to control for verbosity
   differences). A ratio meaningfully above 1.0 relative to English is the signal.
