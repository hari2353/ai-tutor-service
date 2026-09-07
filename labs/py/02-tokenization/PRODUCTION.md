# Production notes — tokenization

## The real tokenizers

| Tokenizer | Family | Notes |
|---|---|---|
| tiktoken (GPT-4o, o-series) | byte-level BPE | exact lab algorithm + a regex pre-split; merges trained once, shipped as data |
| SentencePiece (Llama) | Unigram/BPE over unicode chars | byte-fallback in modern Llama tokenizers for unseen chars |
| HuggingFace tokenizers | BPE/WordPiece/Unigram | Rust impl, parallel encode; what most fine-tunes ship |

Vocab sizes in production: GPT-2 50k, Llama 2 32k, Llama 3 128k, GPT-4o ~200k (o200k_base). Bigger vocabs trade embedding-matrix size for shorter sequences — the seq-len cost curve is the actual decision variable.

## Why the "strawberry" question fails

BPE merges frequent pairs regardless of character counts: "strawberry" may tokenize as ["str","aw","berry"] — the model never sees the r-count as separate characters. Character-level questions probe inside opaque tokens. That's not a reasoning failure; it's an encoding boundary.

## What breaks

| Symptom | Cause | Fix |
|---|---|---|
| Non-English text costs 3-4× tokens | English-heavy merge training | Multilingual vocab training (or byte fallback with seq-len cost) |
| Numbers split inconsistently ("123" vs "4567") | No digit pre-splitting rule | Modern tokenizers split digits into single chars by policy |
| Trailing-space bugs in classification prompts | Space is inside the NEXT word's token | Be deliberate about strip/pre-split in preprocessing |
| Roundtrip corruption | UTF-8 split mid-codepoint by a truncation | Byte-level decode with errors='replace' hides it — test exact roundtrip |
