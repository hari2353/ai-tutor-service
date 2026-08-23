# Production notes — text chunking

## What you'd actually use

| Need | Tool | Note |
|---|---|---|
| Default recursive split | LangChain `RecursiveCharacterTextSplitter` | `chunk_size=4000` chars / `chunk_overlap=200` defaults — almost nobody ships them unmodified |
| Token-true sizing | `SentenceTransformersTokenTextSplitter`, tiktoken-based splitters | Size to the **embedding** model's 512-token cap, not the LLM's context |
| Structure-aware | LlamaIndex `MarkdownNodeParser`, code splitters (`Language.PYTHON`) | Split before `class`/`def`/headings, never mid-function |
| Semantic breakpoints | LlamaIndex `SemanticSplitterNodeParser` | buffer=1, 95th-percentile similarity drop; one embedding call per sentence |
| Tables/PDFs | Unstructured, LlamaParse | Layout-aware extraction serialized to Markdown; naive flattening scrambles tables |

## What the real ones add over yours

- **Token counting, not character counting.** Your `size` is in characters; production splits measure with a real tokenizer because a 4000-char chunk is ~800–1000 tokens but wildly variable.
- **Injectable length functions.** LangChain's splitter takes any `length_function`, so the same ladder serves characters, BPE tokens, or sentence-transformer tokens.
- **Knobs you skipped:** `keep_separator`, `strip_whitespace`, `add_start_index` (offsets for citations). The last one matters more than people expect — retrieval UX needs provenance.
- **Metadata propagation.** Real pipelines carry document title/section headers onto every chunk (contextual retrieval's cheap cousin) so "the company" has an anchor.
- **Memoized merging.** Merging pieces re-measures lengths constantly; production splitters cache prefix lengths.

## What breaks at scale

| Symptom | Cause | Fix |
|---|---|---|
| Chunks exceed the model's input cap anyway | Sized in characters, capped in tokens | Measure with the deployment tokenizer |
| Recall fine in eval, answers cut in half live | Overlap too small or zero | 10–20% of chunk size; verify straddling answers appear whole in some chunk |
| Index full of near-duplicate vectors | Overlap close to size | Cap overlap; dedupe by normalized text before ingest |
| Code retrieval returns half a function | Character-count splitting | Language-aware separators; huge functions → summary + body chunks |
| Silent corpus shrinkage after re-index | Splitter dropped whitespace/separators; nobody checked | Property-test coverage (`assert_no_loss`) in CI |

## Cost & latency

Splitting itself is microseconds per MB — it's pure string work. The costs hide downstream: chunk count drives embedding API spend and vector-store rows roughly as `len(text) / (size - overlap)`; 20% overlap ≈ 25% more embeddings for the same corpus. That multiplier is the honest price of boundary insurance, and it is why "just crank overlap" is not free.

## The 3 questions an interviewer asks after you describe this

1. *"Why is recursive splitting the default almost everywhere?"* — approximates document structure (paragraphs → sentences → words) with zero model calls; semantic chunking only earns its embedding calls when topical boundaries genuinely vary within the doc.
2. *"What does overlap buy, and what does it cost?"* — an answer straddling a boundary survives whole in at least one chunk; cost is storage/embeddings scaled by `size/(size-overlap)`, plus near-duplicate competition in top-k past a point.
3. *"How do you know your splitter didn't lose anything?"* — a stitched-coverage property test over a mixed corpus (this lab's `assert_no_loss`), run in CI like any other invariant.
