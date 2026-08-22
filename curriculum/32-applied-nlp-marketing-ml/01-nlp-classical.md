# Classical NLP: Tokenization, Stemming, TF-IDF, n-grams, POS, Dependency Parsing

> **Track:** T32 Applied NLP & Marketing ML · **Time:** 2.5h · **Prereqs:** T03 Classical ML · **Updated:** 2026-08-02
> **Module id:** `T32-nlp-classical` · **Tags:** nlp, critical

## The 30-second version

Classical NLP is the pipeline that turns raw text into features a statistical model can consume: tokenize, normalize (stem or lemmatize), count (TF-IDF, n-grams), and optionally tag for structure (POS, dependency parse). None of it disappeared when transformers arrived — it moved to different layers of the stack. TF-IDF and BM25 still run as the sparse half of every hybrid retrieval system because they're exact, free of hallucination, and cheap enough to run on every query; tokenization survives inside every LLM as a subword algorithm (BPE, WordPiece, SentencePiece), just no longer whitespace-and-stem; dependency parses still back rule-based extraction where you need deterministic, auditable behavior on a narrow pattern. What died is the hand-built pipeline for open-ended understanding — nobody chains a POS tagger into hand-written rules to do sentiment or intent classification anymore, because a fine-tuned transformer or a zero-shot LLM call is both more accurate and less code to maintain. The interview signal here is knowing exactly which half of that split you're in before reaching for a tool, and being able to say the accuracy and latency numbers that justify the choice.

## Why this gets asked

A Marketing Content ML role lives on top of a content corpus — hotel descriptions, ad copy, reviews, listings — at a scale where every LLM call has a real dollar cost and every batch job has a real latency budget. The interviewer has been the person who shipped a transformer-only pipeline that cost 40x more than the classical baseline for a 2-point F1 gain nobody asked for, or who inherited a search system where TF-IDF was quietly still doing the sparse retrieval underneath a fancy embeddings layer and nobody on the team could explain why. They're checking whether you reach for the heaviest tool by default, or whether you know that a `TfidfVectorizer` plus logistic regression is still the right first baseline for content tagging at scale, and can say precisely when it stops being enough.

---

## Lineage: past → present → future

**What came before.** Rule-based and dictionary-driven NLP (regex extraction, hand-built lexicons, Brill's transformation-based tagger, 1992) dominated through the 1990s because it was the only thing that worked without training data, and it broke constantly on anything outside the rules the author anticipated — a new phrasing, a typo, a domain shift, and precision collapsed. Statistical NLP (HMM POS taggers, Porter stemming, 1980) replaced hand rules with corpus-trained probability, and TF-IDF (Salton & Buckley, 1988, building on Spärck Jones's 1972 IDF insight) gave the field its first durable, still-used representation for document relevance — a term is important to a document if it's frequent there and rare everywhere else. The specific pain this era killed: manually maintaining thousands of if/else rules that only ever covered the cases the author had personally seen.

**Where it stands now.** The field has cleanly split by task. For **retrieval and ranking**, sparse lexical methods didn't lose — BM25 (Robertson & Walker, 1994, an evolution of TF-IDF that adds term-frequency saturation and document-length normalization) is still the default sparse signal in every hybrid search stack in 2026, fused with dense embeddings via reciprocal rank fusion, because it is exact-match-guaranteed, needs no training, and costs microseconds per query. For **classification**, the honest baseline is TF-IDF + logistic regression or linear SVM, and it is embarrassingly close to a fine-tuned BERT on many production text-classification tasks at a fraction of the latency and cost — the gap is real but often not worth paying for at scale. For **tokenization**, whitespace/regex tokenization was replaced inside every modern model by learned subword tokenization (BPE, SentencePiece), because it handles out-of-vocabulary words, morphology, and multilingual text without an explicit stemmer. For **structural analysis**, statistical POS tagging and dependency parsing (transition-based parsers, arc-eager/arc-standard, as implemented in spaCy) are now neural under the hood but the *task framing* — assign a tag per token, assign a head per token — is unchanged since the 2000s, and it still backs rule-based information extraction where a company needs 100% precision on a narrow, auditable pattern (extract the phone number that's the object of a "call us at" dependency relation) that an LLM would answer with slightly different phrasing every time. The live disagreement is whether classical preprocessing is even worth teaching juniors anymore, given that most new pipelines start with an LLM call — practitioners who've shipped at scale say yes, because cost and latency force you back to classical methods the moment volume gets large, and because you can't build the sparse half of hybrid search without it.

**Where it's heading.** High confidence: sparse lexical retrieval keeps its seat in hybrid search indefinitely, because dense embeddings and BM25 fail on different query types (dense loses exact-match rare terms and IDs; BM25 loses paraphrase and cross-lingual queries), and fusing them is now the settled default rather than a debated one. Moderate confidence: LLM-based zero-shot and few-shot classification keeps eating the low-volume, high-value-per-call end of classification (nuanced content moderation, ambiguous intent), while TF-IDF/linear baselines keep the high-volume, cost-sensitive end (bulk content tagging, spam filtering at ingest). Speculative: some argue rule-based dependency-parse extraction will fully give way to structured-output LLM calls as constrained decoding gets cheap enough to run at ingest volume — this is not yet true at the throughput most content pipelines need (thousands of documents/second), and treating it as settled is a mistake an interviewer will catch.

---

## Mental model

```
raw text
   │
   ▼
TOKENIZE  ───────────────  "Expedia's best hotels!" → [Expedia, 's, best, hotels, !]
   │                        (whitespace/regex classical | BPE/WordPiece for LLMs)
   ▼
NORMALIZE ───────────────  stemming: hotels → hotel  (crude, rule-based, fast)
   │                        lemmatization: 's → is / has (needs POS + dictionary)
   ▼
   ├── COUNT ──────────────  TF-IDF / n-grams → sparse vector → linear model, BM25 search
   │
   └── TAG STRUCTURE ──────  POS: best=ADJ, hotels=NOUN
                              dependency: hotels ←(amod)── best
                                          hotels ──(dobj)──→ [verb]
                              → rule-based extraction, syntactic features
```

The one thing to internalize: tokenization and normalization are *lossy compressions* chosen to serve a downstream task, not ground truth. Stemming trades precision for recall and speed. Lemmatization trades speed for correctness. TF-IDF trades word order for a fixed-size vector a linear model can consume. Every choice here is a bet about what information the downstream model actually needs — get the bet wrong and you either starve the model of signal or drown it in noise.

---

## How it actually works

### Tokenization

Classical tokenization splits on whitespace and punctuation with regex rules (`\w+`, contraction handling, hyphenation rules), and it breaks in predictable ways: "New York-based" splits wrong without a compound-noun rule, "don't" needs an explicit contraction table, and any language without whitespace word boundaries (Chinese, Japanese, Thai) needs a completely different approach (dictionary-based segmentation like MeCab or a statistical segmenter). This is why every modern LLM tokenizer abandoned whitespace tokenization for **learned subword tokenization**: Byte-Pair Encoding (BPE, Sennrich et al. 2015) starts from characters and greedily merges the most frequent adjacent pair until it hits a target vocabulary size (commonly 30k-50k for BERT-era models, 100k+ for modern LLMs), which handles out-of-vocabulary words by falling back to smaller subword or byte-level pieces instead of an `<UNK>` token. This is not a classical-NLP relic — it's the direct technical descendant, and interviewers use it to check whether you understand tokenization as one continuous idea rather than "the old way" and "the new way."

### Stemming vs. lemmatization

**Stemming** applies deterministic suffix-stripping rules with no dictionary and no context. The Porter algorithm (Porter, 1980) runs five sequential rule phases, each stripping the longest matching suffix that leaves a stem satisfying a minimum syllable-count condition — e.g. `SSES → SS`, `IES → I`, `ATIONAL → ATE`. Porter2/Snowball (2001) is a more consistent reimplementation and is the version actually shipped in NLTK and most production stemmers today. Stemming is fast (a table lookup plus regex, effectively O(word length)) and language-specific but needs no training data — the cost is that it over-stems (collapses distinct words: "organization" and "organ" can both reduce toward "organ"-like stems in aggressive configurations, "university" and "universe" collide under naive rules) and produces non-words ("running" → "runn" under overly aggressive rules), which is fine for a bag-of-words search index and actively wrong for anything that displays the result to a user.

**Lemmatization** maps a word to its dictionary base form using a vocabulary plus morphological knowledge, and correctness requires knowing the word's part of speech first — "meeting" lemmatizes to "meet" as a verb but stays "meeting" as a noun, so a lemmatizer without a POS tagger upstream silently gets this wrong on ambiguous words. WordNet-based lemmatization (used by NLTK) or the lemmatizer bundled in a POS-tagging pipeline (spaCy) is 10-50x slower than stemming per token because of the dictionary lookup and POS dependency, but it never produces a non-word and it's the right choice whenever the output is read by a human or matched against a controlled vocabulary (a taxonomy of content tags, for instance).

**The failure mode to name in an interview:** an e-commerce search index stemmed "organic" and "organization" to a shared stem in an over-aggressive configuration, and a search for "organic skincare" started surfacing "Organization Studies" articles — the observable symptom is a spike in zero-click or low-relevance-click search sessions with no code change, traced back to a stemmer library upgrade that changed rule aggressiveness. The fix was switching the affected field to lemmatization and reserving stemming for fields where recall matters more than precision (fuzzy internal search, not customer-facing).

### TF-IDF, derived

Term Frequency-Inverse Document Frequency scores how important a term is to a specific document within a corpus. Term frequency for term `t` in document `d`:

```
tf(t, d) = count(t, d)                      # raw count
tf(t, d) = 1 + log(count(t, d))             # log-scaled, the common production choice
```

Log-scaling matters because raw counts overweight repetition — a document that says "hotel" 40 times isn't 40x "more about hotels" than one that says it once, it's saturating. Inverse document frequency penalizes terms that appear in most documents (stopword-like terms carry no discriminative signal):

```
idf(t, D) = log( N / df(t) )                # N = corpus size, df(t) = # docs containing t
idf(t, D) = log( (1 + N) / (1 + df(t)) ) + 1   # smoothed variant (scikit-learn default), avoids
                                                # division by zero and log(0) when a term is in
                                                # every or zero documents
```

TF-IDF score: `tfidf(t, d) = tf(t, d) * idf(t, D)`. Worked example: a 10,000-document corpus, term "boutique" appears in 50 documents, term "the" appears in 9,800. `idf("boutique") = log(10000/50) ≈ 5.30`; `idf("the") ≈ log(10000/9800) ≈ 0.02`. A document mentioning "boutique" twice and "the" twenty times gets a TF-IDF-weighted vector where "boutique" dominates despite the ten-times-lower raw count — this is the entire mechanism, and it's why TF-IDF needs no stopword list to work reasonably (though production pipelines still strip stopwords for vocabulary-size and speed reasons, not correctness). Cosine similarity between two TF-IDF vectors is the standard comparison because it's invariant to document length: `cos(A, B) = (A · B) / (||A|| ||B||)`.

**Where TF-IDF stops being enough, precisely:** it has no notion of term-frequency saturation (a document mentioning a term 100 times scores proportionally, not diminishingly, more relevant) and no document-length normalization beyond the vector-norm division, which underweights how *concentrated* a match is in a short document versus a long one. BM25 fixes both directly:

```
BM25(t, d) = idf(t) * ( tf(t,d) * (k1 + 1) ) / ( tf(t,d) + k1 * (1 - b + b * |d|/avgdl) )
```

`k1` (commonly 1.2-2.0) controls term-frequency saturation — how much a repeated term keeps adding score; `b` (commonly 0.75) controls how strongly document length is penalized. This is why BM25, not raw TF-IDF, is what ships in Elasticsearch/OpenSearch/Lucene's default similarity and every hybrid retrieval stack's sparse leg as of 2026 — know that TF-IDF is the concept and BM25 is the production-hardened version of the same idea, not a separate algorithm.

### n-grams

An n-gram is a contiguous sequence of `n` tokens. Unigrams (single words) lose word order entirely ("not good" and "good not" become identical bag-of-words); bigrams and trigrams recover local order at the cost of vocabulary size exploding combinatorially — a vocabulary of 50,000 unigrams can produce millions of distinct bigrams in a large corpus, most occurring once. Production systems bound this with a minimum document frequency (drop n-grams appearing in fewer than `k` documents) or the hashing trick (`HashingVectorizer`: hash each n-gram into a fixed-size bucket, trading a small, controllable collision rate for a fixed memory footprint independent of vocabulary growth — essential for streaming or online-learning pipelines where you can't pre-fit a vocabulary). Character n-grams (fastText's core idea, covered in the next module) sidestep the whole tokenization problem for morphologically rich languages and typos, at the cost of a much larger effective feature space. n-grams also underpin classical language modeling (Kneser-Ney smoothing, Katz back-off) — mostly obsolete for generation now that neural LMs exist, but the smoothing intuition (never assign zero probability to an unseen sequence) is worth knowing cold because it's the direct ancestor of label smoothing and temperature in modern generation.

### POS tagging

Part-of-speech tagging assigns a grammatical category (noun, verb, adjective, ...) per token, typically against the Penn Treebank tagset (36 POS tags plus punctuation tags) in English. It's a sequence-labeling problem: the tag for "book" depends on context ("book a flight" = verb, "read a book" = noun), which single-token classification can't capture. **HMM taggers** model `P(tag_i | tag_{i-1})` (transition) and `P(word_i | tag_i)` (emission), decoded with the Viterbi algorithm in `O(n * T^2)` time for a sequence of length `n` and `T` possible tags — this was the production standard through the 1990s-2000s. **CRFs** (Conditional Random Fields, Lafferty et al. 2001) improved on HMMs by modeling `P(tags | words)` directly as a globally normalized sequence model with arbitrary overlapping features (word shape, suffix, capitalization, surrounding words), removing the HMM's restrictive independence assumptions — this was the dominant production approach for both POS tagging and NER (see the next module) through roughly 2015. Modern taggers (spaCy's, and the tagging head of any transformer-based pipeline) are neural sequence models, typically a shared transformer or BiLSTM encoder with a per-token classification head, reaching roughly 97%+ token accuracy on English news-domain text and noticeably lower on noisy or out-of-domain text (social media, code-mixed text, low-resource languages) — the accuracy number is domain-dependent, and quoting one figure as universal is a tell that you haven't run it on your own data.

### Dependency parsing

Dependency parsing assigns each token a syntactic head and a relation label (nominal subject, direct object, adjectival modifier, ...), producing a tree rooted at the sentence's main verb. **Transition-based parsers** (arc-standard, arc-eager — the family spaCy's parser descends from) process the sentence left to right with a stack and buffer, at each step choosing SHIFT (move a word onto the stack), LEFT-ARC, or RIGHT-ARC (attach the top of stack to the buffer or vice versa and pop), trained as a classifier over parser states — this runs in linear time, `O(n)`, which is why it's the production choice at scale. **Graph-based parsers** (McDonald et al. 2005, using the Chu-Liu-Edmonds or Eisner algorithm to find the maximum spanning tree over a fully scored graph of all possible head-dependent pairs) are more accurate on long-range dependencies but run in `O(n^2)` to `O(n^3)` depending on the algorithm, because they score every possible arc rather than making local greedy decisions. Evaluation uses **UAS** (Unlabeled Attachment Score — percent of tokens with the correct head, ignoring the relation label) and **LAS** (Labeled Attachment Score — correct head *and* correct relation label); modern neural transition-based parsers on English news text reach roughly 90-95% UAS, with LAS running a few points lower because getting the relation label right is strictly harder than getting the head right. This is the layer that backs rule-based extraction: "find the direct object of any verb whose lemma is 'book' or 'reserve'" is a two-line dependency-tree traversal that never hallucinates and never needs retraining, which is exactly why it survives inside production content pipelines that need deterministic, auditable field extraction.

---

## Build it from scratch

```python
# untested sketch — minimal TF-IDF + logistic regression baseline,
# the actual first thing to try before reaching for a transformer
import re
import math
from collections import Counter

def tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())

def build_vocab_and_idf(docs: list[list[str]]) -> tuple[dict, dict]:
    N = len(docs)
    df = Counter()
    for tokens in docs:
        for term in set(tokens):
            df[term] += 1
    vocab = {term: i for i, term in enumerate(df)}
    idf = {term: math.log((1 + N) / (1 + df[term])) + 1 for term in df}
    return vocab, idf

def tfidf_vector(tokens: list[str], vocab: dict, idf: dict) -> dict[int, float]:
    tf = Counter(tokens)
    vec = {}
    for term, count in tf.items():
        if term in vocab:
            vec[vocab[term]] = (1 + math.log(count)) * idf[term]
    return vec

def cosine_sim(a: dict[int, float], b: dict[int, float]) -> float:
    common = set(a) & set(b)
    dot = sum(a[k] * b[k] for k in common)
    norm_a = math.sqrt(sum(v * v for v in a.values()))
    norm_b = math.sqrt(sum(v * v for v in b.values()))
    return dot / (norm_a * norm_b) if norm_a and norm_b else 0.0

# A minimal Porter-style stemmer step, to see the mechanism (not the full algorithm):
def strip_plural_suffix(word: str) -> str:
    if word.endswith("sses"):
        return word[:-2]                 # caresses -> caress
    if word.endswith("ies") and len(word) > 4:
        return word[:-3] + "y"           # ponies -> pony
    if word.endswith("s") and not word.endswith("ss"):
        return word[:-1]                 # cats -> cat
    return word
```

The three things this skips that a real system needs: a fitted `min_df`/`max_df` vocabulary cutoff (production TF-IDF drops terms in fewer than ~2-5 documents and more than ~80-95% of documents), sublinear TF scaling consistently applied at both fit and transform time, and — for anything beyond a toy corpus — a sparse matrix representation (`scipy.sparse`) rather than Python dicts, since a real vocabulary is 50k-200k terms and a dense representation would be catastrophic.

---

## How it's done in production

**scikit-learn** (`TfidfVectorizer`, `CountVectorizer`, `HashingVectorizer`) — the reference implementation for classical text features in Python; fast, well-tested, and the correct first stop for any tabular-style text classification task. **spaCy** — the reference production pipeline for tokenization, POS tagging, dependency parsing, and (next module) NER, with pretrained pipelines per language (`en_core_web_sm/md/lg/trf`) trading model size and accuracy against latency. **NLTK** — the teaching and prototyping library (Porter/Snowball stemmers, WordNet lemmatizer, classic POS taggers); rarely the production choice today because spaCy's pipelines are faster and better-maintained, but its stemmers are still what most people mean when they say "Porter stemmer" in Python. **Elasticsearch/OpenSearch/Lucene** — BM25 is the default similarity scoring function, meaning every full-text search deployment on these engines is running the production-hardened descendant of TF-IDF whether or not the team knows it. **Hugging Face `tokenizers`** — the reference BPE/WordPiece/SentencePiece implementation backing essentially every modern LLM tokenizer.

| Symptom | Cause | Fix |
|---|---|---|
| Search relevance degrades after a stemmer library upgrade, no code change | Stemming rule aggressiveness changed, distinct words now collapse to the same stem | Pin stemmer version; for customer-facing fields, switch to lemmatization, which never merges distinct dictionary words |
| TF-IDF classifier accuracy drops sharply on a new content batch | Vocabulary drift — the fitted vocabulary from training doesn't cover new terms (new hotel brand names, new slang) | Refit periodically on a rolling window; monitor out-of-vocabulary rate on incoming documents as a leading indicator, not just downstream accuracy |
| Search returns long, barely-relevant documents above short, highly relevant ones | Using raw TF-IDF cosine similarity with a corpus of highly variable document lengths and no term-frequency saturation | Move to BM25, which explicitly penalizes document length via the `b` parameter and saturates repeated-term scoring via `k1` |
| POS tagger accuracy is far below the quoted benchmark number | Domain mismatch — tagger trained on news text, applied to social media, product reviews, or a non-English/code-mixed corpus | Fine-tune or retrain on in-domain labeled data; never assume a published accuracy number transfers across domains without measuring |
| Dependency-parse-based extraction rule misses valid cases after a parser model upgrade | Parser retrained on a different treebank version/annotation scheme, dependency labels shifted slightly | Pin the parser model version in production; add a regression test suite of known sentence/extraction pairs that runs on every model upgrade |
| Feature matrix memory blows up during training | Unbounded n-gram vocabulary on a large or streaming corpus | Apply `min_df`/`max_df` cutoffs, or switch to `HashingVectorizer` with a fixed bucket count |

---

## Tradeoffs & when NOT to use it

- **Don't use stemming anywhere a human reads the output.** Non-words in a customer-facing UI ("runn", "organiz") are an instant credibility hit; reserve stemming for internal search indices and IR pipelines where only the match matters, not the display.
- **Don't use raw TF-IDF for search ranking if you can use BM25 instead.** There's no real reason to: BM25 is a strict, well-understood improvement for the same cost, already the default in every mainstream search engine, and the "TF-IDF vs BM25" framing in an interview is really "do you know the production-hardened version exists."
- **Don't build a rule-based dependency-parse extraction pipeline for open-ended understanding tasks.** It's the right tool for a narrow, stable, high-precision pattern (extract a phone number, a price, a date from a specific syntactic construction); it's the wrong tool for anything where the phrasing space is genuinely open, where an LLM's flexibility earns its cost.
- **Don't reach for a fine-tuned transformer as the first baseline.** Always fit TF-IDF + linear model first — it trains in seconds, gives you a real accuracy floor, and on many production content-tagging tasks the transformer gain is a few F1 points for 10-100x the latency and infra cost. If the linear baseline is within your tolerance, ship it.
- **Don't trust a single quoted POS/parsing accuracy number across domains.** Every accuracy figure in this module is a news-domain or general-web number; social media text, code-mixed text, and specialized vocabularies (travel/hospitality terminology, for a company like Expedia) can drop accuracy meaningfully, and the only honest answer in an interview is "I'd measure it on our data before trusting the published number."

---

## Interview questions

### Q1 — Walk me through the TF-IDF formula and derive why the IDF term uses a log.
**Testing:** whether you understand TF-IDF as a derived idea, not a memorized formula.
**Answer:** `tf(t,d)` measures local importance (log-scaled to avoid overweighting repetition — `1 + log(count)`), `idf(t,D) = log(N/df(t))` measures global rarity. The log compresses IDF's range so a term appearing in 1 of 10,000 documents doesn't dominate by a factor of 10,000 versus one appearing in 100 — without the log, IDF grows linearly with rarity and swamps the TF signal for any moderately rare term, producing scores dominated by noise (rare misspellings, unique IDs) rather than genuinely discriminative terms.
**Follow-up trap:** *"Why the +1 smoothing in scikit-learn's default IDF?"* — avoids division by zero when a term appears in every document and log(0) when computing a term absent from the fit vocabulary at transform time; naming the specific numerical failure, not just "it's for stability," is what separates a real answer.

### Q2 — When would you choose TF-IDF over BM25, if ever?
**Answer:** Rarely for ranking — BM25 dominates it at the same cost. TF-IDF earns its place as a fixed-size feature vector for classification/clustering (cosine similarity between document vectors, k-means, logistic regression input), a role BM25 wasn't designed for since BM25 is a query-document scoring function, not a general vector representation.
**Follow-up trap:** *"So BM25 could never feed a classifier?"* — you could construct BM25-weighted term vectors, but nobody does, because TF-IDF's vector-space framing is simpler to reason about for classification and the saturation/length-normalization BM25 adds matters specifically for query-time ranking, not for a fixed feature matrix.

### Q3 — Stemming or lemmatization for a search index over hotel descriptions?
**Answer:** Depends on what's shown to the user. If matches are surfaced only internally (a candidate-generation stage before reranking), stemming's speed and recall win. If the matched term or a snippet is shown to a customer, lemmatization avoids non-word artifacts. Many production systems stem for the retrieval index and lemmatize (or don't normalize at all) for the display layer — naming this split is the senior answer.
**Follow-up trap:** *"What if stemming merges two genuinely distinct brand names?"* — that's the over-stemming failure mode; the fix is a stopword/protected-term list for proper nouns and brand names that bypasses the stemmer entirely, since a generic rule-based stemmer has no notion of "this is a brand, don't touch it."

### Q4 — Explain the difference between HMM, CRF, and neural sequence taggers for POS tagging.
**Answer:** HMMs model transition and emission probabilities generatively (`P(tag|prev_tag) * P(word|tag)`) and decode with Viterbi in `O(n*T^2)`; they assume each word depends only on its own tag, which limits feature richness. CRFs model `P(tags|words)` discriminatively with arbitrary overlapping features (word shape, affixes, context window) and no independence assumption between observations, which is why they beat HMMs on the same task. Neural taggers (BiLSTM or transformer encoder plus a per-token classification head) learn the feature representation instead of hand-engineering it, and are now standard because they need less feature engineering and generalize better across domains given enough data.
**Follow-up trap:** *"Are CRFs obsolete, then?"* — no; a linear-chain CRF trained on a modest labeled set is still a legitimate production choice when you need a lightweight, fast, CPU-only tagger with no GPU dependency and interpretable per-feature weights, especially in cost-constrained or low-latency-budget deployments.

### Q5 — What does UAS vs LAS actually tell you about a dependency parser, and why does LAS trail UAS?
**Answer:** UAS is the percent of tokens attached to the correct head, ignoring relation labels; LAS additionally requires the relation label to be correct. LAS trails because getting the head right (structural attachment) is a coarser decision than getting the specific grammatical relation right (e.g., distinguishing a direct object from an indirect object attached to the same head) — LAS is strictly harder, so LAS ≤ UAS always.
**Follow-up trap:** *"Which metric matters for a rule-based extraction pipeline?"* — LAS, because extraction rules key off specific relation labels (`dobj`, `nsubj`, `amod`), not just structural attachment; a parser with high UAS but weak LAS will attach the right words together but mislabel the relationship your rule is looking for, silently breaking the extraction.

### Q6 — Design a content-tagging system for hotel descriptions at high volume. Would you use classical NLP or an LLM?
**Testing:** whether you reach for the heaviest tool by default.
**Answer:** Start with TF-IDF + a linear classifier (logistic regression, one-vs-rest for multi-label tags) as the baseline — it trains and infers cheaply enough to run on every ingested document, gives an immediate accuracy floor, and is fully debuggable via feature weights. Route only the genuinely ambiguous cases (low classifier confidence, novel vocabulary) to an LLM call, and use those LLM labels to retrain the classifier over time. Full LLM tagging on every document only makes sense if volume is low enough that cost/latency don't bind, which is rarely true at "every hotel description on the platform" scale.
**Follow-up trap:** *"What if the tag taxonomy changes frequently?"* — that favors the LLM path more (zero-shot doesn't need retraining per taxonomy change), but the honest middle ground is a hybrid: LLM-label a sample to bootstrap or update the classifier's training data whenever the taxonomy shifts, rather than fully switching architectures.

### Q7 — What's wrong with using raw word counts (no TF-IDF) as classifier input?
**Answer:** High-frequency, low-information words (stopwords, common domain terms like "hotel" in a hotel-description corpus) dominate the feature space by magnitude, drowning the discriminative signal from rarer, more informative terms. Raw counts also don't correct for document length — a longer document has proportionally larger counts for every term regardless of topical relevance.
**Follow-up trap:** *"Doesn't removing stopwords fix this without needing IDF?"* — partially, but IDF is a continuous, corpus-adaptive version of stopword removal that also downweights domain-specific high-frequency terms a generic stopword list wouldn't catch (e.g., "hotel" itself, in a hotel-description corpus) — stopword lists are a blunt, manually maintained special case of what IDF does automatically.

### Q8 — How would you handle out-of-vocabulary words in a TF-IDF pipeline versus a modern tokenizer?
**Answer:** A fitted TF-IDF vocabulary is fixed at training time; any term not seen during fit is simply dropped at transform time, losing that signal entirely — this is a real, silent failure mode if vocabulary drift is significant. Subword tokenizers (BPE/WordPiece) sidestep this by decomposing any unseen word into known subword pieces (falling back to characters or bytes in the worst case), so there's no true OOV token, only a longer, less efficient encoding of a novel word.
**Follow-up trap:** *"So should TF-IDF pipelines use subword tokenization too?"* — you can build a TF-IDF-over-subwords or character-n-gram representation (this is close to what fastText does, see the next module) to get partial OOV robustness, at the cost of a much larger effective vocabulary and features that are individually less interpretable than whole-word TF-IDF weights.

### Q9 — A dependency-parse-based extraction rule that worked for a year suddenly starts failing on 15% of documents. How do you debug it?
**Answer:** First check whether the parser model itself changed (library upgrade, retrained pipeline) — dependency label sets and attachment conventions can shift subtly between model versions, silently breaking rules that pattern-match specific relation labels. Second, check whether the input distribution shifted (a new content source with different sentence structure). Pull the failing 15% and manually inspect the parse trees against the rule's assumptions rather than guessing.
**Follow-up trap:** *"How do you prevent this in the future?"* — pin the parser model version explicitly in production dependencies, and maintain a regression test suite of known sentence → expected-extraction pairs that runs on every model or library upgrade before it ships, exactly the way you'd regression-test any other silently-versioned dependency.

### Q10 — Explain BPE tokenization and why it replaced whitespace tokenization for neural models.
**Answer:** BPE starts from individual characters and greedily merges the most frequent adjacent symbol pair, repeating until the vocabulary reaches a target size (commonly 30k-50k for BERT-era encoders, larger for modern decoder LLMs). This produces subword units that balance vocabulary size against sequence length, and critically, it never produces a true out-of-vocabulary token — any string decomposes into known pieces down to individual bytes/characters in the worst case. Whitespace tokenization can't do this: a word not seen during vocabulary construction is either dropped or mapped to a generic `<UNK>`, losing information.
**Follow-up trap:** *"Does BPE handle morphology well?"* — inconsistently; it's a frequency-driven statistical procedure with no linguistic knowledge, so it sometimes splits a word at a linguistically meaningful morpheme boundary and sometimes doesn't, purely based on corpus frequency. This is a real known limitation, not a solved problem, and claiming BPE "understands morphology" is a red flag.

### Q11 — What's term-frequency saturation, and why does BM25 need it but TF-IDF doesn't have it?
**Answer:** Saturation means additional occurrences of a term contribute diminishing marginal score rather than linear score. TF-IDF's log-scaled TF (`1 + log(count)`) provides a crude version of this, but BM25 makes it an explicit, tunable curve via `k1`: as `tf(t,d) → ∞`, the BM25 term-frequency component approaches `k1 + 1`, a hard ceiling, whereas log-scaled TF keeps growing (slowly) without bound. This matters because a document mentioning a term 200 times due to keyword stuffing shouldn't score proportionally higher than one mentioning it 20 times if both are clearly about the topic.
**Follow-up trap:** *"What does k1=0 mean?"* — it collapses the term-frequency component to a constant regardless of how many times the term appears (pure presence/absence scoring), which is a legitimate configuration for boolean-ish relevance signals, showing you understand `k1` as a genuine dial rather than a magic default.

### Q12 — Your linear TF-IDF classifier and a fine-tuned transformer are within 1.5 F1 points of each other on your content-tagging task. Which do you ship?
**Testing:** the senior tradeoff signal.
**Answer:** Ship the TF-IDF model unless there's a specific reason not to — at production content volume the latency and infra cost difference (single-digit milliseconds and CPU-only versus tens of milliseconds and GPU/accelerated inference) usually dwarfs a 1.5-point F1 gain in business value, and the linear model's feature weights are directly inspectable for debugging misclassifications, which the transformer's aren't without extra tooling.
**Follow-up trap:** *"What would change your answer?"* — if the 1.5 points sit on a business-critical decision boundary (e.g., content moderation where false negatives have compliance risk), or if the task genuinely needs context the bag-of-words representation can't capture (negation, sarcasm, long-range dependency between clauses), the accuracy gain can be worth the cost — the answer has to name the specific condition, not just assert cost always wins.

### Q13 — What's the vocabulary-size explosion problem with n-grams, and how do production systems bound it?
**Answer:** Unigram vocabularies are already tens of thousands of terms; bigrams multiply that combinatorially, and most bigrams in a large corpus occur once, contributing almost no signal while inflating the feature matrix. Production systems bound this with `min_df` (drop n-grams below a minimum document frequency), `max_features` (keep only the top-N by frequency or TF-IDF score), or the hashing trick (hash n-grams into a fixed number of buckets, accepting a small collision rate in exchange for a memory footprint independent of vocabulary size).
**Follow-up trap:** *"What's the downside of the hashing trick specifically?"* — hash collisions are silent and unrecoverable — you can't inspect which original terms landed in a given bucket after the fact, which breaks feature-importance interpretability entirely; it's the right choice for streaming/online learning where you can't pre-fit a vocabulary, and the wrong choice when you need to explain a model's decisions to a stakeholder.

### Q14 — How would you detect that a production TF-IDF classifier's vocabulary has gone stale?
**Answer:** Track the out-of-vocabulary rate on incoming documents (fraction of tokens not in the fitted vocabulary) as a leading indicator — a rising OOV rate predicts accuracy degradation before it shows up in downstream metrics, especially in a domain like marketing content where new brand names, campaign terms, and product lines appear continuously. Pair it with a scheduled or drift-triggered refit on a rolling recent window.
**Follow-up trap:** *"What if refitting the vocabulary changes feature indices and breaks a downstream model that assumed a fixed feature space?"* — this is exactly why production pipelines pin vocabulary artifacts to a model version and refit-plus-retrain together rather than swapping the vocabulary under a frozen model; treat vocabulary and model as one versioned unit.

### Q15 — Design the preprocessing pipeline for a multilingual content corpus (English, Spanish, German, Japanese).
**Testing:** synthesis and awareness that classical NLP tooling doesn't transfer uniformly across languages.
**Answer:** Tokenization can't be a single regex — Japanese has no whitespace word boundaries and needs a dedicated segmenter (MeCab or a statistical segmenter), German's compound nouns ("Handschuhschneeballwerfer") need either a compound-splitter or subword tokenization to avoid an exploding vocabulary of unique compounds, and Spanish needs its own stemmer/lemmatizer resources (Snowball supports it, but accent and diacritic normalization needs explicit handling). The realistic production answer at this scale is to use a multilingual subword tokenizer (SentencePiece, trained jointly across languages) feeding a multilingual model, rather than maintaining four separate classical pipelines — but say explicitly that classical stemming/lemmatization resources are not uniformly available or equally mature across languages, and that's a real constraint, not a detail to gloss over.
**Follow-up trap:** *"Would you still use TF-IDF for search across all four languages?"* — yes for the sparse leg per-language (a Japanese-segmented, Japanese-specific TF-IDF/BM25 index is still valuable for exact-match retrieval), but cross-lingual semantic search needs a multilingual dense embedding model layered on top, since TF-IDF has no notion of cross-language term equivalence at all.

---

## Red flags that fail you

- Calling TF-IDF and BM25 the same algorithm, or not knowing BM25 exists.
- Claiming stemming and lemmatization are interchangeable, or that stemming never produces non-words.
- Quoting a single POS-tagging or dependency-parsing accuracy number as universal across domains.
- Not knowing IDF needs a log transform and why (unbounded linear scaling on rare terms).
- Reaching for a fine-tuned transformer as the default first baseline instead of a linear TF-IDF model.
- Describing BPE as "just splitting on subwords" without the frequency-driven merge mechanism.
- Not knowing the difference between UAS and LAS, or claiming they're always equal.
- Assuming a classical NLP pipeline built for English transfers unchanged to a language without whitespace word boundaries.

---

## Cheat card

```
TOKENIZE   whitespace/regex (classical) vs BPE/WordPiece/SentencePiece (subword, no true OOV)
           BPE: greedy merge of most-frequent adjacent pair, vocab 30k-50k typical (BERT-era)

STEM       Porter (1980)/Snowball(2001): rule-based suffix stripping, no dict, can produce
           non-words, over-stems (organization~organ). Fast: O(len). Use for internal search only.
LEMMA      dictionary + POS-dependent (meeting->meet[verb] vs meeting[noun]). 10-50x slower.
           Use whenever output is human-facing.

TF-IDF     tf = 1 + log(count)              [log-scaled, avoids overweighting repetition]
           idf = log((1+N)/(1+df)) + 1      [sklearn default, smoothed]
           tfidf = tf * idf
BM25       adds saturation (k1, ~1.2-2.0) + length norm (b, ~0.75). Default in ES/OpenSearch/Lucene.
           BM25 > raw TF-IDF for ranking, always, same cost. TF-IDF still used as fixed feature vector.

N-GRAMS    vocab explodes combinatorially past unigrams. Bound with min_df/max_features or
           HashingVectorizer (fixed buckets, silent collisions, loses interpretability).

POS        HMM: P(tag|prev)*P(word|tag), Viterbi O(n*T^2). CRF: discriminative, arbitrary features.
           Neural (spaCy/transformer): ~97%+ on English news text, domain-dependent, MEASURE IT.
DEP PARSE  transition-based (arc-eager/standard): O(n), spaCy's approach, production default.
           graph-based (MST/Eisner): O(n^2-n^3), better long-range accuracy.
           UAS = correct head. LAS = correct head AND label. LAS <= UAS always. ~90-95% UAS typical.

BASELINE RULE   always fit TF-IDF + linear model first. Only pay for a transformer if the F1
                gain justifies 10-100x latency/cost at your actual volume.
```

## Sources

- [TF-IDF: A Statistical Interpretation — Spärck Jones, 1972 / Salton & Buckley, 1988 (Wikipedia summary)](https://en.wikipedia.org/wiki/Tf%E2%80%93idf) — accessed 2026-08-02
- [BM25 vs TF-IDF: Which Ranks Text Better and Why? — MLWorks/Medium](https://medium.com/mlworks/why-bm25-algorithm-over-tf-idf-67bc009d20de) — accessed 2026-08-02
- [scikit-learn TfidfVectorizer documentation](https://scikit-learn.org/stable/modules/generated/sklearn.feature_extraction.text.TfidfVectorizer.html) — accessed 2026-08-02
- [spaCy linguistic features (POS, dependency parsing)](https://spacy.io/usage/linguistic-features) — accessed 2026-08-02
- [Neural Architectures for Named Entity Recognition — Lample et al., 2016 (background on CRF vs neural sequence tagging)](https://arxiv.org/abs/1603.01360) — accessed 2026-08-02
- [Machine Learning Scientist III, NLP at Expedia Group — WORK180 (Bayesian, LDA, NER, Random Forests requirements)](https://work180.com/en-us/for-women/employer/expedia/job/458598/machine-learning-scientist-iii-nlp) — accessed 2026-08-02
- [Neural Word Segmentation Learning for Chinese (background on non-whitespace tokenization)](https://arxiv.org/abs/1606.04300) — accessed 2026-08-02
- [Porter, M.F. (1980) An algorithm for suffix stripping](https://tartarus.org/martin/PorterStemmer/) — accessed 2026-08-02

## Changelog
- 2026-08-02 — created
