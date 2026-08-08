# Tokenization vs Stemming vs Lemmatization, Stopwords, Normalization, TF-IDF

> **Track:** T06 RAG · **Time:** 2.0h · **Prereqs:** none · **Updated:** 2026-08-01
> **Module id:** `T06-text-preprocessing` · **Tags:** ingest,critical

## The 30-second version

Classical NLP preprocessing — tokenize, lowercase, strip stopwords, stem or lemmatize, then score with TF-IDF or BM25 — was built for a world where "similarity" meant "shares surface word forms," and most of that pipeline is now the wrong default for dense embedding retrieval, because embeddings already encode semantic similarity and aggressive normalization destroys exactly the signal (word order, morphology, casing, punctuation) that a transformer learned to use. What's still load-bearing: subword tokenization (BPE/WordPiece/SentencePiece) is mandatory for any neural model, Unicode normalization (NFC) prevents silent retrieval failures from byte-level mismatches, and BM25 — TF-IDF's successor with saturation and length normalization — remains the strongest lexical leg of every production hybrid-search stack. Stemming and lemmatization are precise, different operations: stemming chops affixes by rule (fast, produces non-words, language-agnostic-ish), lemmatization maps to a dictionary form using part-of-speech (slower, correct, needs a language model) — and both matter far less to a transformer-based system than they did to a bag-of-words one. The one rule that separates people who've shipped multilingual retrieval from people who haven't: never run aggressive stemming, case-folding, or stopword removal ahead of a dense embedding model, because the tokenizer and the embedding model were trained on natural text, not your "cleaned" version of it.

## Why this gets asked

The interviewer has debugged a retrieval system where someone ported a classical NLP preprocessing pipeline — stem everything, strip stopwords, lowercase — directly in front of a BGE or OpenAI embedding call, and watched recall drop because the embedding model had never seen text that mangled. Or they've watched a multilingual product silently degrade for non-English users because the team's stemmer only existed for English and Spanish, and every other locale got either no normalization or a broken one. They want to know whether you can tell "this preprocessing step is still doing real work" from "this is 2005-era cargo cult applied to a 2026 embedding model," and whether you understand what actually breaks retrieval at the byte level (Unicode) versus the token level (tokenization) versus the semantic level (embeddings).

---

## Lineage: past → present → future

**What came before.** Pre-neural information retrieval (1970s-2000s) represented documents as bags of words scored by exact term overlap. The pain this preprocessing pipeline was built to solve was purely lexical: "running," "runs," and "ran" needed to count as matches for a query about "run," and without some normalization step, exact string matching missed all of them. Stemming (Porter, 1980) and later lemmatization solved this by reducing surface variation before indexing. Stopword removal solved a different, adjacent problem: "the," "a," "is" appear in nearly every document, so they contribute almost no discriminative signal to a bag-of-words match but inflate index size and dilute term-frequency statistics — removing them was a straightforward win when your entire notion of relevance was term overlap. TF-IDF (Salton & Buck, 1988, formalizing earlier work) gave this pipeline a scoring function: weight a term by how often it appears in this document, discounted by how common it is across all documents, so rare, distinguishing terms score higher than ubiquitous ones.

**Where it stands now.** The field split cleanly into two regimes that get preprocessed completely differently. **Lexical/sparse retrieval** (BM25 and its production deployments in Elasticsearch, OpenSearch, Lucene) still uses a version of this classical pipeline — tokenize, lowercase, sometimes stem, sometimes remove stopwords — because it's scoring exact and near-exact term matches, and normalization genuinely increases the recall of the term-matching function it's built on. **Dense/neural retrieval** (embedding a chunk with a transformer, `T06-embeddings-choice`) inverted the recommendation: the tokenizer for a modern embedding model is a fixed subword vocabulary (BPE/WordPiece/SentencePiece) baked into pretraining, so you don't get to choose whether to tokenize, you feed the model text close to what it was trained on, and hand-rolled stemming or stopword removal ahead of that tokenizer actively hurts, because it produces token sequences the model never saw during training. Hybrid search (`T06-hybrid-search`) runs both legs in parallel precisely because they fail in opposite ways and neither preprocessing regime should be forced onto the other's retriever. The live disagreement is mostly about how much lexical preprocessing survives even for the BM25 leg in a modern hybrid stack — some production systems skip stemming even for BM25 now, on the theory that the dense leg already covers morphological variation and the lexical leg's whole job is to catch *exact* identifiers, error codes, and rare terms where stemming would be actively counterproductive (stemming "iOS17" or a SKU code destroys the exact match you needed it for).

**Where it's heading.** High confidence: subword tokenization keeps its position as the universal, non-optional first step for any neural model — no serious 2026 architecture uses whole-word or character-only tokenization. High confidence: classical stemming/stopword-removal pipelines keep shrinking to a niche (pure-BM25 systems, some non-neural analytics) rather than disappearing outright, because BM25 itself isn't disappearing — it remains cheap, exact, and complementary to dense retrieval. Moderate confidence: as multilingual embedding models improve, the "which languages have decent stemmers" problem that plagues classical pipelines becomes increasingly moot for the systems that matter, since dense retrieval sidesteps stemming's language-coverage problem entirely by learning morphology implicitly from data rather than from hand-written rules — but this is a bet on model quality closing the gap, not yet a universally settled result across all 22+ locales a real system might serve.

---

## Mental model

```
CLASSICAL PIPELINE (built for bag-of-words / lexical matching)

  raw text -> tokenize -> lowercase -> remove stopwords -> stem/lemmatize -> TF-IDF/BM25 score
                                                                                     │
                                                                    still load-bearing for
                                                                    the LEXICAL leg of retrieval

NEURAL PIPELINE (built for a transformer that already learned morphology + semantics)

  raw text -> Unicode normalize (NFC) -> subword tokenize (BPE/WordPiece/SentencePiece)
                                                    │
                                          feed DIRECTLY to the model
                                          (no stemming, no stopword removal,
                                           no aggressive lowercasing — the model
                                           was trained on natural text, not "cleaned" text)

  MOST CLASSICAL STEPS ARE NOW ACTIVELY HARMFUL HERE, not merely unnecessary —
  they produce token sequences the embedding model never saw in training.
```

---

## How it actually works

### Tokenization vs stemming vs lemmatization — stated precisely

These three operations are frequently confused; they do genuinely different things at different granularities.

| Operation | What it does | Speed | Output | Example |
|---|---|---|---|---|
| **Tokenization** | Splits text into units (words, subwords, or characters) — a segmentation step, not a normalization step | Fast | Tokens, same information content as input, just chunked | `"running fast"` → `["running", "fast"]` |
| **Stemming** | Chops affixes off a word using fixed heuristic rules (no dictionary, no context) | Very fast | Often a non-word | `"running"` → `"run"`, but `"universal"` → `"univers"` (Porter stemmer artifact) |
| **Lemmatization** | Maps a word to its dictionary base form (lemma), using part-of-speech and often morphological analysis | Slower — needs a POS tagger or language model | Always a real word | `"running"` (verb) → `"run"`; `"better"` (adjective) → `"good"` (a stemmer cannot do this — there's no shared substring) |

The Porter stemmer (1980) and Snowball (its successor, supporting more languages) are rule-based: strip known suffix patterns in a fixed sequence of steps, with no awareness of whether the result is a real word or whether the word's part of speech even permits that suffix to mean what the rule assumes. This is why stemming is fast (no lookup, no model) but crude — "universal" and "university" can stem to overlapping forms despite being semantically unrelated, and "saw" (past tense of "see") won't stem toward "see" at all, because there's no shared suffix pattern for a stemmer to exploit.

Lemmatization needs to know the word's part of speech to resolve ambiguity correctly — "meeting" as a noun lemmatizes to "meeting," as a verb (progressive of "meet") lemmatizes to "meet" — which is why a real lemmatizer either requires a POS tag as input or runs a POS tagger internally, making it meaningfully slower than a stemmer's fixed rule table.

**When each is right.** Stemming: high-throughput lexical indexing where speed matters more than precision and false-positive term matches are tolerable (classic web search era BM25 indexing). Lemmatization: anywhere correctness of the base form matters more than speed and you have the POS-tagging budget — but in 2026, for anything feeding a neural model, the honest answer is usually "neither, feed the raw text to the subword tokenizer."

### Stopwords, and why removing them breaks phrase and semantic search

Stopword removal drops high-frequency, low-information words ("the," "a," "is," "of") before indexing, on the theory that they rarely discriminate between documents in a bag-of-words match. This breaks two things a classical pipeline didn't originally have to worry about:

1. **Phrase search.** "The Who" (the band) with stopwords removed becomes just "Who" — an entirely different, much more common query, with completely different correct results. Removing "the" destroyed the query's actual meaning.
2. **Semantic search with dense embeddings.** A transformer's attention mechanism uses function words for structure and disambiguation — "not," a canonical stopword in older lists, flips a sentence's meaning entirely, and removing it before embedding would erase a negation. Stopword lists built for 1990s bag-of-words retrieval frequently include exactly the words a modern model needs to correctly resolve meaning.

Production systems either skip stopword removal entirely ahead of dense retrieval, or, if they still run it for a BM25 leg, use a much shorter, more conservative list than the classical NLTK/SMART lists, explicitly excluding negations and words known to matter for the query patterns the product actually sees.

### Case folding, Unicode normalization, and mojibake

**Case folding.** Lowercasing before indexing increases recall for exact-match lexical search ("Apple" the query should match "apple" the document) but destroys a real signal for tasks where case carries meaning — "US" (country) vs "us" (pronoun), or code identifiers where case is semantically load-bearing. Modern subword tokenizers are typically case-sensitive by design (`bert-base-cased` exists specifically because lowercasing loses information some tasks need), so the decision to fold case is task-specific, not a universal default.

**Unicode normalization.** The same visual character can have multiple valid byte representations — "é" can be a single precomposed codepoint (U+00E9) or an "e" followed by a combining accent (U+0065 U+0301). These are visually identical and semantically identical, but byte-for-byte different, so a naive exact-match or hash-based dedup step will treat them as different strings. **NFC** (Normalization Form Canonical Composition) converts to the precomposed form; **NFKC** (Normalization Form Canonical Composition, compatibility) additionally folds compatibility characters (full-width vs half-width forms, ligatures, certain typographic variants) into a canonical equivalent. Production text pipelines should normalize to NFC (or NFKC if compatibility folding is acceptable for the domain) *before* tokenization, hashing, or deduplication — otherwise two byte-different-but-visually-identical strings silently fail to match, and this shows up as a real, silent retrieval failure: a document containing the precomposed form doesn't get retrieved by a query typed with the decomposed form, with no error, no exception, just a missing result.

**Mojibake.** This is the observable failure mode of a Unicode/encoding mismatch: text decoded with the wrong character encoding produces garbage characters that look like corrupted symbols (`Ã©` instead of `é`, or a string of `�` replacement characters). In retrieval, mojibake shows up as documents that embed or tokenize into meaningless garbage tokens, degrading both the lexical index (garbage terms that never match anything) and the embedding (a vector representing noise rather than the document's actual content). The fix is enforcing UTF-8 end-to-end (ingestion, storage, indexing) and normalizing at the ingestion boundary, not downstream — by the time mojibake reaches your embedding model, the original bytes are already unrecoverable in the general case.

### TF-IDF, derived

TF-IDF scores how important a term is to a specific document relative to a collection. Term frequency alone is a bad signal — a word appearing 10 times in a document isn't necessarily 10x as important, and common words appear frequently in every document regardless of relevance. TF-IDF corrects for this:

```
TF(t, d)  = count of term t in document d  (often log-dampened: 1 + log(count))
IDF(t)    = log( N / df(t) )
            where N = total documents, df(t) = number of documents containing t
TF-IDF(t, d) = TF(t, d) * IDF(t)
```

The intuition: a term appearing in every document (`df(t) = N`) gets `IDF = log(1) = 0` — it contributes nothing to the score, which is exactly the stopword-removal insight, arrived at algorithmically instead of via a hand-curated list. A rare term appearing in only a handful of documents gets a large IDF, so when it does appear in a document, it dominates that document's score — which is the right behavior, since rare shared terms are strong relevance signals.

**Why TF-IDF alone isn't enough, and what BM25 fixes.** TF-IDF's raw term frequency grows unboundedly — a document repeating a term 100 times scores far higher than one repeating it 10 times, even though the marginal 90 repetitions add little additional evidence of relevance past a point. BM25 (Robertson & Jones, developed through the 1990s Okapi system) adds two corrections:

```
BM25(D, Q) = Σ_{t in Q}  IDF(t) * ( f(t,D) * (k1 + 1) ) / ( f(t,D) + k1 * (1 - b + b * |D| / avgdl) )

  f(t,D)   = raw term frequency of t in document D
  |D|      = length of document D (in tokens)
  avgdl    = average document length across the corpus
  k1       ≈ 1.2-2.0  — controls term-frequency saturation
  b        ≈ 0.75      — controls length-normalization strength (0 = no normalization, 1 = full)
```

**Saturation (`k1`).** As `f(t,D)` grows, the term `f(t,D)*(k1+1) / (f(t,D)+k1)` asymptotically approaches `k1+1` rather than growing linearly — the 10th occurrence of a term adds much less score than the 1st, which matches the real-world intuition that a document isn't 10x more relevant just because a term was repeated 10 times.

**Length normalization (`b`).** A long document has more chances to contain any given term simply by being long, not because it's more relevant. The `|D|/avgdl` factor penalizes documents longer than average and rewards documents shorter than average, controlled by `b` — at `b=0` there's no length penalty at all, at `b=1` it's fully normalized. `b=0.75` is the long-standing default because it empirically balances these without over-penalizing legitimately long, relevant documents. This is why BM25, not raw TF-IDF, is the lexical scoring function in essentially every production search system today — full derivation of its role in hybrid fusion (RRF, score combination with dense retrieval) lives in `T06-hybrid-search`, not repeated here.

### Why subword tokenization replaced word tokenization for neural models

Word-level tokenization needs a fixed vocabulary of whole words, and any word not in that vocabulary becomes `<UNK>`, destroying information with no recovery path — a typo, a rare technical term, a name, or most forms of a morphologically rich language collapse into the same unrecoverable symbol. Character-level tokenization has no OOV problem but makes sequences very long and forces the model to relearn word structure from scratch at every layer, wasting context length and capacity on a solved problem. Subword tokenization (BPE, WordPiece, SentencePiece — full algorithmic detail in `T05-tokenization`) sits between these: common words stay as single tokens for efficiency, rare or unseen words decompose into meaningful subword pieces (or, worst case, individual bytes/characters), so there is no true OOV token and no unrecoverable information loss. This is a completely settled architectural default; every serious neural model in 2026 uses some subword tokenization variant.

### The multilingual reality — a real constraint on 22-locale work

Stemmers and lemmatizers are hand-built, per-language resources requiring linguistic expertise to construct correctly — the Porter/Snowball family covers a few dozen languages well, and coverage drops off sharply outside them; for many languages spoken by hundreds of millions of people, no maintained, high-quality stemmer exists at all, and hand-rolling one is a multi-month linguistics project, not a quick script. This matters directly for any system doing preprocessing-then-search across a large locale set: if your pipeline's correctness depends on stemming, you have silently different quality per language, with no stemmer at all for some of them, and that's a production correctness gap most teams don't discover until a specific-locale bug report arrives. This is the strongest practical argument for pushing multilingual systems toward dense embeddings (which learn cross-lingual morphological structure directly from data, with no hand-built per-language rules to maintain or omit) rather than classical stem-then-lexical-match pipelines, and for treating BM25's role in a multilingual hybrid stack as "catch exact tokens and identifiers" rather than "do linguistically correct morphological matching" in every locale.

### When NOT to preprocess

The senior-signal answer to this whole module: **with dense embeddings, aggressive normalization destroys signal.** A transformer-based embedding model was trained on natural, unmodified text — casing, punctuation, word order, and morphological variation are all information the model learned to use, not noise to be scrubbed. Concretely:
- Lowercasing before a case-sensitive embedding model erases a distinction the model relies on.
- Stemming before tokenization feeds the model token sequences (`"univers"`, `"organ"`) that never appeared in its training data, degrading the quality of the resulting embedding in ways that are hard to detect without a targeted eval, because the model still produces *a* vector, just a worse one.
- Stopword removal before embedding can flip meaning (negations) or destroy the syntactic structure attention relies on.
- Aggressive punctuation stripping loses sentence boundaries, list structure, and code-block delimiters that matter for chunking quality upstream of embedding (`T06-chunking`).

The right amount of preprocessing for a dense-embedding pipeline is close to none: Unicode-normalize (NFC), strip genuinely non-content artifacts (control characters, encoding errors), and otherwise feed the model text as close to its natural form as your source data allows.

---

## Build it from scratch

```python
# untested sketch — minimal TF-IDF and BM25 for comparison
import math
from collections import Counter

def tf_idf(term, doc_tokens, corpus_token_lists):
    N = len(corpus_token_lists)
    df = sum(1 for toks in corpus_token_lists if term in toks)
    if df == 0:
        return 0.0
    idf = math.log(N / df)
    tf = doc_tokens.count(term)
    return tf * idf

def bm25(term, doc_tokens, corpus_token_lists, k1=1.5, b=0.75):
    N = len(corpus_token_lists)
    df = sum(1 for toks in corpus_token_lists if term in toks)
    if df == 0:
        return 0.0
    idf = math.log((N - df + 0.5) / (df + 0.5) + 1)      # BM25's smoothed IDF variant
    f = doc_tokens.count(term)
    avgdl = sum(len(toks) for toks in corpus_token_lists) / N
    dl = len(doc_tokens)
    denom = f + k1 * (1 - b + b * dl / avgdl)
    return idf * (f * (k1 + 1)) / denom if denom else 0.0

def score_query(query_terms, doc_tokens, corpus_token_lists, fn=bm25):
    return sum(fn(t, doc_tokens, corpus_token_lists) for t in query_terms)
```

```python
# untested sketch — Unicode normalization at the ingestion boundary
import unicodedata

def normalize_for_indexing(text: str) -> str:
    text = unicodedata.normalize("NFC", text)   # canonical composition — do this BEFORE tokenizing
    return text

def is_stemmed_wrong_for_embeddings(pipeline_step: str) -> bool:
    # sanity check to run in code review: is a classical step sitting in front of an embedding call?
    return pipeline_step in {"porter_stem", "snowball_stem", "stopword_removal", "aggressive_lowercase"}
```

---

## How it's done in production

| Tool/approach | What it adds |
|---|---|
| Elasticsearch / OpenSearch / Lucene analyzers | Configurable tokenizer + filter chain (lowercase, stopword, stemmer) for the BM25 leg; production-hardened, per-language analyzer configs |
| `nltk`, `spaCy` | Lemmatization with POS tagging, per-language models; used where lexical correctness matters more than raw throughput |
| Hugging Face `tokenizers` (Rust-backed) | Fast subword tokenization matching a specific pretrained model's vocabulary exactly — the only tokenization that matters ahead of a neural model |
| `unicodedata` (stdlib) / ICU | Unicode normalization (NFC/NFKC) at the ingestion boundary |
| BM25 in a hybrid stack | See `T06-hybrid-search` for RRF fusion with dense retrieval and production engine specifics (Elasticsearch, Weaviate, Vespa) |

**Failure modes**

| Symptom | Cause | Fix |
|---|---|---|
| Query and document with visually identical characters silently don't match | Unicode normalization mismatch (NFC vs NFD forms of the same text) | Normalize to NFC (or NFKC) at ingestion, before tokenization/hashing/indexing, consistently on both query and document paths |
| Embedding-based retrieval quality drops after a "cleanup" preprocessing step is added | Stemming/stopword-removal/aggressive lowercasing feeding token sequences the embedding model never saw in training | Remove classical normalization ahead of the embedding call; feed near-raw text |
| Phrase queries return wrong or irrelevant results | Stopwords stripped from a phrase query, changing its meaning ("The Who" → "Who") | Preserve stopwords for phrase-query paths, or use a much shorter, curated stopword list |
| Retrieval quality is wildly inconsistent across locales | Stemmer/lemmatizer only exists (or is high-quality) for a subset of the 22+ languages served | Move morphological normalization burden onto the dense retrieval leg; restrict BM25-side preprocessing to exact-token matching where a stemmer would help without a per-locale coverage gap |
| Documents ingested from a legacy system look like garbage in the index (`Ã©`, `�`) | Mojibake — text decoded with the wrong character encoding upstream | Enforce UTF-8 end-to-end; fix decoding at the ingestion boundary, not downstream — the original bytes are often unrecoverable once corrupted |
| BM25 relevance scores don't reflect intuitive term importance despite reasonable TF-IDF weighting | No saturation or length normalization — a long document or repeated term dominates unfairly | Switch from raw TF-IDF to BM25 with `k1≈1.2-2.0`, `b≈0.75` |

---

## Tradeoffs & when NOT to use it

- **Don't run stemming or lemmatization ahead of a dense embedding call.** The embedding model was trained on natural text; feeding it stemmed non-words or lemmatized forms produces a worse embedding, and this is one of the more common, hard-to-detect bugs in RAG ingestion pipelines because nothing throws an error — you just get subtly worse retrieval.
- **Don't remove stopwords ahead of anything that needs to understand negation or phrase structure** — dense embeddings, phrase queries, and any downstream generation step that reads the retrieved chunk as natural language.
- **Don't assume a stemmer exists, or is good, for every locale you serve.** At 22-locale scale, this assumption silently degrades quality for whichever languages your team didn't personally test, and it's a real, documented gap for many non-Latin-script and morphologically rich languages.
- **Do keep BM25 and its lexical preprocessing** for the retrieval leg that specifically needs to catch exact identifiers, error codes, SKUs, and rare technical terms — this is exactly where stemming and dense embeddings both underperform, and it's why hybrid search exists rather than picking one leg.
- **When preprocessing is genuinely still the right call**: pure lexical/BM25-only systems with no dense leg, log-analytics-style exact-term search, or languages/domains where a mature, high-quality stemmer exists and throughput matters more than the marginal precision lemmatization would add.

---

## Interview questions

### Q1 — Precisely distinguish tokenization, stemming, and lemmatization.
**Answer:** Tokenization segments text into units (a splitting operation, no information loss). Stemming chops affixes via fixed rules with no dictionary or context, is fast, and can produce non-words ("universal" → "univers"). Lemmatization maps a word to its dictionary base form using part-of-speech, is slower because it needs a POS tagger or language model, and always produces a real word.
**Follow-up trap:** *"Give an example a stemmer can't handle but a lemmatizer can."* — "better" → "good" (adjective comparative to base form) or "saw" → "see" (irregular past tense). Neither has a shared substring for a rule-based stemmer to exploit; both require dictionary/POS knowledge only a lemmatizer has.

### Q2 — Why does removing stopwords break phrase and semantic search?
**Answer:** For phrase search, removing a stopword can change the query's meaning entirely ("The Who" without "the" becomes just "Who," a completely different, more common query). For semantic search with dense embeddings, function words carry structural and disambiguating signal a transformer's attention relies on — "not" is a classic stopword whose removal erases a negation.
**Follow-up trap:** *"So should you ever remove stopwords?"* — for a pure BM25/lexical leg where you're specifically optimizing term-overlap scoring and not feeding a neural model, a short, conservative stopword list (excluding negations) can still be a reasonable throughput/index-size optimization; the mistake is applying classical stopword lists unmodified ahead of dense retrieval.

### Q3 — Derive TF-IDF and explain each term's purpose.
**Answer:** `TF(t,d)` counts how often term t appears in document d — raw frequency, sometimes log-dampened. `IDF(t) = log(N/df(t))` discounts terms that appear in many documents, since ubiquitous terms carry little discriminative signal; a term in every document gets `IDF=0` and contributes nothing. Multiplying them weights a term high only when it's both frequent in this document and rare across the corpus — exactly the profile of a genuinely distinguishing term.
**Follow-up trap:** *"What's wrong with TF-IDF that BM25 fixes?"* — TF-IDF's raw term frequency grows unboundedly, so a term repeated 100 times scores far higher than repeated 10 times even though the marginal repetitions add little relevance evidence, and it has no document-length normalization, so long documents score higher just by having more chances to contain any given term.

### Q4 — Walk through BM25's two correction terms and their typical values.
**Answer:** Saturation via `k1` (typically 1.2-2.0): the term-frequency component `f*(k1+1)/(f+k1)` asymptotically approaches `k1+1` rather than growing linearly, so additional repetitions of a term add diminishing score. Length normalization via `b` (typically 0.75): the `|D|/avgdl` factor penalizes documents longer than the corpus average, since length alone increases the chance of containing any given term; `b=0` disables this entirely, `b=1` fully normalizes.
**Follow-up trap:** *"What happens if you set b=0?"* — you get pure term-frequency saturation with no length penalty at all, which then over-favors long documents purely because they have more opportunities to contain query terms — a common misconfiguration when someone copies a BM25 default without understanding what `b` controls.

### Q5 — Why did subword tokenization replace whole-word tokenization for neural models?
**Answer:** Whole-word tokenization needs a fixed vocabulary; any out-of-vocabulary word (typos, rare terms, names, many morphologically rich language forms) collapses into an unrecoverable `<UNK>` token, destroying information. Character-level tokenization has no OOV problem but produces very long sequences and forces the model to relearn word structure from scratch at every layer. Subword tokenization (BPE/WordPiece/SentencePiece) sits between them — common words stay single tokens, rare words decompose into meaningful pieces, and there's no true OOV case since any string decomposes to bytes/characters as a fallback.
**Follow-up trap:** *"Does this mean stemming is now pointless?"* — not pointless, but largely superseded for neural pipelines: a subword tokenizer already handles "running"/"runs"/"ran" sharing subword pieces implicitly through training, without a hand-written rule, and without producing non-words the model never saw.

### Q6 — What's mojibake, and where does it show up in a retrieval pipeline?
**Answer:** Mojibake is the garbled output of decoding text with the wrong character encoding — visually corrupted characters like `Ã©` instead of `é`, or replacement-character strings (`�`). In retrieval it shows up as documents that tokenize and embed into meaningless garbage, silently degrading both the lexical index (garbage terms matching nothing) and the embedding (a vector for noise, not content), with no thrown error to flag it.
**Follow-up trap:** *"Can you fix mojibake after the fact?"* — sometimes, if the original encoding is known and the corruption is a simple systematic mis-decode (there are heuristic re-encoding fixes), but in general once you've re-encoded through the wrong path and lost information, it's not reliably recoverable — the real fix is enforcing UTF-8 end-to-end at ingestion, not patching downstream.

### Q7 — Why does NFC vs NFD Unicode normalization cause silent retrieval bugs?
**Answer:** The same visual character can have multiple valid byte representations — a precomposed codepoint (NFC) versus a base character plus combining marks (NFD). These are visually and semantically identical but byte-different, so exact-match, hashing, or naive tokenization treats them as different strings. A query typed in one normalization form silently fails to match a document stored in the other, with no error.
**Follow-up trap:** *"Where exactly should normalization happen in the pipeline?"* — at the ingestion boundary, applied consistently to both the indexing path and the query path, before tokenization or hashing — normalizing only one side (e.g. documents but not queries) reintroduces the exact mismatch you were trying to fix.

### Q8 — Your team added a "text cleanup" step (lowercase, strip punctuation, stem) ahead of your embedding model and retrieval quality dropped. Why, and what do you do?
**Testing:** the core senior signal of this module.
**Answer:** The embedding model was trained on natural, unmodified text; feeding it lowercased, stemmed, punctuation-stripped text produces token sequences and casing/structure patterns it never saw in training, degrading embedding quality in a way that's easy to miss because the model still returns *a* vector, just a worse one. Fix: remove classical normalization ahead of the embedding call, keep only Unicode normalization and genuine artifact removal (control characters, encoding errors).
**Follow-up trap:** *"What if you need that cleanup for your BM25 leg?"* — that's fine and often correct — apply classical preprocessing only on the lexical leg's index/query path, never on the path feeding the embedding model; the two legs of a hybrid system legitimately want different preprocessing.

### Q9 — Your product serves 22 locales. Why is a classical stem-then-search pipeline a real production risk here specifically?
**Answer:** Stemmers and lemmatizers are hand-built, per-language linguistic resources; high-quality coverage exists for a few dozen languages and drops off sharply outside them, with no maintained stemmer at all for many languages spoken by hundreds of millions of people. A pipeline whose correctness depends on stemming has silently different quality per locale, and that gap typically isn't discovered until a specific-language bug report arrives.
**Follow-up trap:** *"How would you mitigate this without a stemmer for every language?"* — push morphological normalization onto the dense embedding leg, which learns cross-lingual structure from data rather than hand-written rules, and restrict the lexical/BM25 leg's job to exact-token matching (identifiers, codes, rare terms) where stemming was never the right tool regardless of language.

### Q10 — Give a concrete example of a term that should NOT be stemmed, and why.
**Answer:** A SKU code or version identifier like "iOS17" — stemming rules aren't aware of exact-identifier semantics and can mangle it toward something that no longer matches the literal string a user or document actually contains, destroying the exact match that identifier-style lexical search depends on. This is part of why some production hybrid systems skip stemming even on the BM25 leg, reserving that leg specifically for exact and near-exact term matching.
**Follow-up trap:** *"Isn't that what stopword lists and stemmers are supposed to avoid by design?"* — no, stemmers apply their rules uniformly by surface pattern; they have no way to distinguish "a common English word that benefits from normalization" from "an exact identifier that must not be touched" without a separate identifier-detection step, which most classical pipelines don't include.

### Q11 — When would you still choose a pure BM25 lexical system with full classical preprocessing over adding a dense embedding leg?
**Answer:** When queries are dominated by exact-term matching needs (log search, code search, structured-data lookup) where semantic paraphrase matching adds little value relative to its cost, when the corpus and query patterns are well-served by a mature stemmer for the languages involved, or when the latency/cost budget can't support an embedding model at all (edge deployment, extremely high QPS with tight cost constraints).
**Follow-up trap:** *"Users are complaining they can't find results when they paraphrase their query. Does that change your answer?"* — yes, that's the textbook symptom of a lexical-only system's failure mode (blind to paraphrase), and it's the direct argument for adding a dense retrieval leg and moving to hybrid search rather than tuning BM25 further, since BM25 structurally cannot solve zero-term-overlap paraphrase matching.

---

## Red flags that fail you

- Using "tokenization," "stemming," and "lemmatization" interchangeably.
- Recommending stemming or stopword removal ahead of a dense embedding model without qualification.
- Not knowing BM25 has saturation and length-normalization terms that TF-IDF lacks.
- Treating Unicode normalization as an edge case rather than a real, silent production failure mode.
- Assuming a stemmer exists and works well for every language a multilingual product serves.
- Describing subword tokenization as optional or a stylistic choice rather than the mandatory neural-model default.
- No answer for "when should you NOT preprocess."

---

## Cheat card

```
TOKENIZE vs STEM vs LEMMATIZE
  tokenize:   split into units — no info loss, fast
  stem:       rule-based affix chop, fast, CAN PRODUCE NON-WORDS ("universal"->"univers")
  lemmatize:  dictionary base form via POS, slower, ALWAYS a real word
              stemmer can't do "better"->"good" or "saw"->"see" — no shared substring

STOPWORDS: removing breaks phrase search ("The Who"->"Who") and negation ("not")
  -> skip entirely ahead of dense embeddings; short/conservative list only for pure BM25

UNICODE
  NFC = canonical composed form; NFKC = + compatibility folding (full-width, ligatures)
  normalize BOTH query and doc path, at ingestion, BEFORE tokenize/hash
  mojibake = wrong-encoding decode garbage (Ã©, �) — fix at ingestion, often unrecoverable after

TF-IDF
  TF(t,d) = count(t in d)     IDF(t) = log(N/df(t))    score = TF*IDF
  term in every doc -> IDF=0 -> contributes nothing (algorithmic stopword removal)

BM25 (TF-IDF's successor — the production lexical scorer)
  score = sum IDF(t) * f*(k1+1) / (f + k1*(1-b+b*|D|/avgdl))
  k1 ≈ 1.2-2.0  -> term-freq SATURATION (10th occurrence << 10x score of 1st)
  b  ≈ 0.75     -> LENGTH NORMALIZATION (0=none, 1=full)

SUBWORD TOKENIZATION (BPE/WordPiece/SentencePiece) — mandatory for every neural model
  word-level: <UNK> collapses OOV, loses info irrecoverably
  char-level: no OOV, but very long sequences, wastes capacity
  subword: common words = 1 token, rare words decompose, no true OOV

MULTILINGUAL REALITY (22-locale relevance)
  stemmers exist well for a few dozen langs, barely/not at all for many others
  -> push morphology onto dense embeddings; BM25 leg = exact-token matching only

WHEN NOT TO PREPROCESS
  dense embeddings: near-RAW text only (NFC normalize + strip genuine artifacts)
  stemming/case-fold/stopword-removal ahead of an embedding call = active harm, not neutral
```

## Sources
- BM25 formalization: Robertson & Zaragoza, *The Probabilistic Relevance Framework: BM25 and Beyond* (2009) — standard IR reference, no version-dependent claim
- TF-IDF: Salton & Buck (1988) foundational formalization — standard IR reference, no version-dependent claim
- [Understanding Embeddings with ModernBERT: pooling and preprocessing](https://medium.com/@ismailvanak/understanding-embeddings-with-modernbert-comparing-mean-pooling-via-transformers-and-300ef0d6b87a) — accessed 2026-08-01

## Changelog
- 2026-08-01 — created
