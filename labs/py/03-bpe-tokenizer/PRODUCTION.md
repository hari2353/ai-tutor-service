# Production notes — BPE tokenization

## What you'd actually use

| Need | Tool | Note |
|---|---|---|
| The real thing | Hugging Face `tokenizers` (Rust core) | Training + encode/decode at production speed, same BPE family |
| Pretrained vocabs | `tiktoken`, `AutoTokenizer` | GPT/Llama families; never retrain a vocab for inference |
| Counting before shipping | `tiktoken.length` / `len(tokenizer.encode(...))` | The #1 cost-estimation primitive |

## What production adds over yours

- **Trained on scale**: real merges come from billions of tokens with byte-level fallback — the lab's corpus is a few dozen strings.
- **Special-token policy**: `<|im_start|>`-style tokens are grammar, not text; the encode path splits on them before BPE sees the pieces.
- **Fuzzy decode**: truncated token sequences must decode lossily (a dangling surrogate) — production tokenizers carry explicit invalid-byte policy.
- **Vocab pinning**: a model checkpoint pins its tokenizer version; retraining silently changes every prompt's token count and breaks cached KV stores.

## What breaks at scale

| Symptom | Cause | Fix |
|---|---|---|
| Non-English costs 3-4x tokens | Legacy BPE trained on English | Modern byte-level vocabs (GPT-4o+, Llama 3) close most of the gap |
| Context "off by one" vs provider count | Different tokenizer than the provider's | Use the provider's tokenizer for budget math, yours for display |
| Same text, different tokens after upgrade | Vocab retrained in a deploy | Pin tokenizer version per model contract |
| Emoji/math split into 5+ tokens | Byte fallback path | Nothing to fix — know the tax when estimating context |

## The one-liner to remember

Tokenization is a learned compression table; the model never sees your
string, only your token ids — and the id budget is the real context budget.
