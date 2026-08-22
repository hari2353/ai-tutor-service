# Word2Vec Derived (CBOW/Skip-gram), GloVe, fastText — and Why Contextual Won

> **Track:** T32 Applied NLP & Marketing ML · **Time:** 2.5h · **Prereqs:** T32-nlp-classical · **Updated:** 2026-08-02
> **Module id:** `T32-word-embeddings` · **Tags:** nlp, critical

## The 30-second version

Word2Vec learns a dense vector per word by training a shallow network to predict context from a word (skip-gram) or a word from its context (CBOW), and the trick that made it fast enough to train on billions of tokens was negative sampling — replacing an expensive softmax over the whole vocabulary with a binary classification between real and randomly sampled fake context words. GloVe reaches a similar representation from the opposite direction: it builds an explicit word-word co-occurrence matrix from the corpus and factorizes it directly with a weighted least-squares objective, so where Word2Vec is prediction-based and online, GloVe is count-based and batch. fastText fixes both models' blindness to morphology and out-of-vocabulary words by representing a word as the sum of its character n-gram vectors, so "unhappiness" shares subword structure with "happy" and a never-before-seen word still gets a usable vector. All three assign exactly one vector per word type, which is the property that killed static embeddings as the default: they can't distinguish "bank" the river feature from "bank" the financial institution, and contextual embeddings (ELMo, then BERT) fixed that by computing a different vector per token occurrence, conditioned on the sentence. Static embeddings survive anyway wherever a forward pass through a transformer costs more than the accuracy is worth — precomputed lookup tables at microsecond latency, zero GPU cost, and genuinely interpretable nearest neighbors are real advantages contextual embeddings don't have.

## Why this gets asked

The interviewer wants to know two separate things in one question: can you derive the actual training objective rather than gesture at "words that appear in similar contexts get similar vectors," and do you know when reaching for a 400M-parameter encoder is a waste of a perfectly good afternoon. They've likely watched a team burn a GPU budget running BERT over a batch job that a fastText model handles in a fraction of the time with acceptable accuracy loss, or debugged a similarity search that returned nonsense because someone assumed a static embedding understood polysemy it structurally cannot represent.

---

## Lineage: past → present → future

**What came before.** Before dense embeddings, word representation meant one-hot vectors or the raw co-occurrence counts and TF-IDF vectors from the previous module — sparse, high-dimensional (vocabulary-sized), and carrying no notion of similarity: "hotel" and "resort" are as distant as "hotel" and "spreadsheet" in a one-hot space, because the representation encodes identity, not meaning. Latent Semantic Analysis (LSA, Deerwester et al. 1990) was the first serious attempt to fix this — SVD on a term-document matrix to produce dense, lower-dimensional vectors — and it worked reasonably for topic-level similarity but was expensive to update (any new document required a full matrix recomputation) and captured document-level co-occurrence rather than fine-grained word-level semantics. The pain that killed this generation: representations that couldn't answer "is 'king' to 'man' as 'queen' is to 'woman'" and couldn't be trained incrementally on a streaming corpus.

**Where it stands now.** Word2Vec (Mikolov et al., 2013) and GloVe (Pennington et al., 2014) settled the question of how to get dense, semantically meaningful word vectors cheaply, and fastText (Bojanowski et al., 2017) settled the morphology and OOV gap both left open. Then the field split, cleanly, by what the task needs. **Contextual embeddings won for anything where meaning depends on context** — ELMo (Peters et al., 2018) first showed that a bidirectional LSTM's internal states, taken per-token, beat static vectors by disambiguating polysemy; BERT (Devlin et al., 2018) then made the transformer version the standard, and every modern LLM's internal representations are contextual embeddings by construction. **Static embeddings kept their seat wherever the cost of a forward pass isn't justified** — real-time systems needing microsecond lookups, resource-constrained or on-device inference, and any pipeline where the interpretability of a fixed, inspectable vector space matters more than context sensitivity. The live disagreement isn't "which is better" (contextual wins on accuracy essentially everywhere it's been benchmarked) — it's "how much accuracy are you willing to pay real latency and infrastructure cost for," and reasonable engineers land in different places depending on their traffic volume and SLA.

**Where it's heading.** High confidence: static embeddings continue as a distillation target and a cost-tier fallback rather than a frontier research direction — nobody is publishing new static embedding architectures, but production systems keep precomputing and shipping them because the economics don't change. Moderate confidence: matryoshka and other truncatable embedding techniques (train once, serve at multiple dimensions) are blurring the line between "static, cheap" and "contextual, accurate" by letting teams dial dimensionality per latency budget rather than choosing a wholly different model family. Speculative: some argue that as inference cost keeps falling, static embeddings eventually become a historical footnote outside of edge/on-device deployment — this has been predicted since 2019 and static embeddings are still shipping in production search and recommendation systems in 2026, so treat the "static embeddings are dead" claim skeptically until the cost curve actually crosses over for your specific latency budget.

---

## Mental model

```
STATIC (one vector per word type, fixed forever after training)

  "bank"  ──────────────▶  [0.12, -0.44, 0.81, ...]     ← SAME vector whether
                                                             "river bank" or
                                                             "bank account"

CONTEXTUAL (one vector per token occurrence, computed at inference time)

  "I sat by the river bank"      → bank → [0.55, 0.02, -0.31, ...]
  "I opened a bank account"      → bank → [-0.18, 0.71, 0.09, ...]
                                             ▲
                                    different vectors, same word,
                                    because the surrounding context
                                    is part of the computation

Word2Vec:  predict from local context window (prediction-based, online, streams over the corpus)
GloVe:     factor global co-occurrence counts (count-based, batch, sees corpus-wide statistics)
fastText:  word vector = sum of its character n-gram vectors (subword-aware, handles OOV)
```

The one thing to internalize: static embeddings are a *lookup table* — training produces a matrix, inference is a row index. Contextual embeddings are a *function* — training produces a model, inference is a forward pass. That's the entire cost and capability tradeoff in one sentence: a lookup table can't know what sentence it's in, and a forward pass can't be free.

---

## How it actually works

### Skip-gram, derived

Skip-gram's goal: given a word `w_t`, predict the words in its surrounding context window of size `c`. The training objective is to maximize the average log probability:

```
J = (1/T) * Σ_t  Σ_{-c ≤ j ≤ c, j≠0}  log p(w_{t+j} | w_t)
```

The naive way to define `p(w_O | w_I)` (output/context word given input/center word) is a softmax over the entire vocabulary:

```
p(w_O | w_I) = exp(v'_{w_O} · v_{w_I}) / Σ_{w=1}^{V} exp(v'_w · v_{w_I})
```

`v_w` is the "input" embedding (word as center), `v'_w` is the "output" embedding (word as context) — two separate embedding matrices during training, and production almost always keeps only `v_w` at the end. The problem: computing that denominator requires a dot product against every one of `V` vocabulary vectors, for every single training example — for a 100,000+ word vocabulary trained on billions of tokens, this is computationally infeasible.

**Negative sampling** (Mikolov et al., 2013) replaces the softmax with a much cheaper binary classification: for each observed (center, context) pair, is this pair real, or is the context word one of `k` randomly sampled "negative" words that don't actually appear near the center word? The objective per training example becomes:

```
log σ(v'_{w_O} · v_{w_I})  +  Σ_{i=1}^{k} E_{w_i ~ P_n(w)} [ log σ(−v'_{w_i} · v_{w_I}) ]
```

`σ` is the sigmoid function. The first term pushes the real (center, context) pair's dot product up (toward "this is a real pair"); the second term pushes `k` randomly sampled fake pairs' dot products down. This turns an `O(V)` computation into an `O(k)` computation per example — with `k` typically 5-20 for smaller datasets and 2-5 for large ones, this is the entire reason Word2Vec could train on a billion-word corpus in hours rather than weeks.

The noise distribution `P_n(w)` matters and is a specific, non-obvious empirical finding: raising the unigram frequency distribution to the **3/4 power** (`P_n(w) ∝ count(w)^0.75`) works better than sampling proportional to raw frequency or uniformly — the exponent dampens the dominance of extremely frequent words (like "the") in the negative samples while still oversampling frequent words relative to uniform, giving a better balance of easy and hard negatives than either extreme.

**CBOW** (Continuous Bag of Words) runs the same idea in reverse: predict the center word from the *averaged* vector of its context words, rather than predicting each context word individually from the center. CBOW is faster to train (it makes one prediction per window instead of `2c` predictions) and tends to do better on frequent words because averaging smooths out noise; skip-gram is slower but typically performs better on rare words and smaller datasets because it treats each (center, context) pair as an independent training signal rather than diluting rare words into an average.

### The deeper theoretical result

Levy & Goldberg (2014) proved that skip-gram with negative sampling is implicitly factorizing a word-context matrix whose cells are the pointwise mutual information (PMI) between word and context, shifted by `-log(k)`:

```
v_{w_I} · v'_{w_O}  ≈  PMI(w_I, w_O) − log(k)
```

This is the theoretical bridge to GloVe: Word2Vec's prediction-based training and GloVe's explicit count-based factorization are solving structurally related problems, just approached from opposite directions — one implicitly via gradient descent on local prediction, one explicitly via direct matrix factorization of global counts. Knowing this connection is a strong interview signal because it shows you understand these aren't two unrelated algorithms that happen to produce similar vectors.

### GloVe, derived

GloVe (Pennington et al., 2014) starts by building an explicit word-word co-occurrence matrix `X`, where `X_ij` counts how often word `j` appears in the context window of word `i`, across the whole corpus. The insight GloVe adds over a naive factorization: **ratios of co-occurrence probabilities encode meaning better than raw probabilities**. For "ice" and "steam" with a probe word "solid," `P(solid|ice)/P(solid|steam)` is large (solid relates to ice much more than steam); with a probe word "gas," the ratio is small; with a neutral probe word like "water," the ratio is close to 1. GloVe's objective is built to make the dot product of two word vectors approximate the log of their co-occurrence count:

```
J = Σ_{i,j=1}^{V}  f(X_ij) * (w_i · w̃_j + b_i + b̃_j − log X_ij)²
```

`w_i` and `w̃_j` are the word and context embedding vectors (again, two matrices, typically averaged or summed at the end), `b_i`/`b̃_j` are bias terms, and `f(X_ij)` is a weighting function that prevents the objective from being dominated by extremely frequent co-occurrences and from wasting gradient signal on co-occurrences that never happened:

```
f(x) = (x / x_max)^α   if x < x_max
f(x) = 1                otherwise
```

with `x_max = 100` and `α = 0.75` as the values from the original paper — note the same 3/4 exponent showing up again as an empirically-good dampening factor, independently discovered in both Word2Vec's negative sampling and GloVe's weighting function. The practical difference from Word2Vec: GloVe requires a full pass to build the co-occurrence matrix before training starts (batch, not online/streaming), and it directly leverages global corpus statistics rather than only ever seeing local windows — in practice, on standard word-analogy and similarity benchmarks the two methods land close to each other, and the choice between them in production is usually about tooling and pretrained-vector availability rather than a measured accuracy gap.

### fastText, derived

fastText (Bojanowski et al., 2017, Facebook AI Research) addresses the problem both prior methods share: they assign one opaque vector per whole word, so morphologically related words ("happy," "unhappy," "happiness") share no structure in the representation, and a word never seen during training has no vector at all. fastText represents each word as a **bag of character n-grams**, typically `n = 3` to `6`, plus a special whole-word token, and the word's final vector is the **sum** of the vectors of all its n-grams:

```
"where" (n=3,4,5) → <wh, whe, her, ere, re>, <whe, wher, here, ere>, <wher, where, here>, ...
                     plus the whole-word token <where>
v_word = Σ (n-gram vectors)
```

(angle brackets mark word boundaries so that "her" as a full n-gram of "where" is distinguishable from the standalone word "her"). Training uses the same skip-gram-with-negative-sampling machinery as Word2Vec, just with the center word's representation computed as this n-gram sum instead of a single lookup. Two direct consequences: morphologically related words share n-grams and therefore share representation structure automatically, without any explicit morphological rules, and **out-of-vocabulary words get a usable vector** by summing the n-grams of the unseen word against the trained n-gram embedding table — this is the single biggest practical advantage over Word2Vec/GloVe for any noisy, informal, or morphologically rich text (social media, product listings with typos and brand-name variants, agglutinative languages like Finnish or Turkish). The cost: the effective vocabulary of n-grams is much larger than the word vocabulary, so fastText models are larger on disk and slightly slower to train and to look up (summing multiple n-gram vectors per word instead of one lookup) than plain Word2Vec.

### Why contextual embeddings won

All three methods above share a structural limitation: **one vector per word type**, computed once at training time and frozen. This cannot represent polysemy — "bank" gets exactly one vector regardless of whether the sentence is about a river or a checking account, which means any downstream model relying on that vector inherits the ambiguity as noise. ELMo (Peters et al., 2018) was the first widely-adopted fix: run a bidirectional LSTM language model over the sentence and use its internal hidden states, per token, as the word's representation — the vector for "bank" is now a function of the actual sentence it appears in, computed at inference time, not looked up from a fixed table. BERT (Devlin et al., 2018) replaced the BiLSTM with a transformer encoder trained with masked language modeling, and pushed accuracy far enough on downstream benchmarks (GLUE score jumps of several points across nearly every task) that contextual embeddings became the default assumption for any new NLP system within about two years. The reason this is not a close call on pure accuracy: word sense disambiguation, coreference-sensitive tasks, and anything where surrounding context changes meaning are all structurally unsolvable by a static lookup table, no matter how much training data you throw at it — the limitation is architectural, not a data or scale problem.

### Where static embeddings still make sense — honestly

This is the part interviewers listen for, because it's where junior candidates default to "just use BERT embeddings for everything" and senior candidates name a real constraint:

- **Latency.** A static embedding lookup is an array index — microseconds, no model inference at all. A contextual embedding requires a forward pass through a multi-layer transformer, commonly single-digit to tens of milliseconds even with a small model and batching, and meaningfully more without a GPU. For any system doing embedding lookups in a tight request-response loop at high QPS (autocomplete, real-time query expansion), this difference is often the entire latency budget.
- **Cost.** Static embeddings are precomputed once and stored; serving is free beyond the storage and lookup cost. Contextual embeddings mean either paying for inference on every request or precomputing embeddings for every possible context, which for open-ended text (user queries) isn't possible — you can't precompute a contextual embedding for a query nobody has typed yet.
- **Interpretability.** A static embedding space has fixed, inspectable nearest neighbors — "what's closest to 'boutique'?" has one stable answer you can audit, log, and explain to a non-technical stakeholder. A contextual embedding's nearest neighbors depend on the sentence it was computed in, which makes debugging "why did the model treat these two things as similar" much harder to reason about in the abstract.
- **Simplicity of downstream use.** Static embeddings compose cleanly with simple linear models and classical ML pipelines (average word vectors as a document feature, feed to logistic regression) without needing a full deep learning serving stack.

The honest framing: static embeddings are the right choice when the task doesn't need context sensitivity (broad topical similarity, coarse query expansion, item2vec-style embeddings over structured event sequences rather than natural language at all) and the latency/cost budget is tight; contextual embeddings are the right choice whenever meaning genuinely depends on surrounding words and the budget allows a forward pass. Most production systems in 2026 use both in different layers of the same pipeline — a static or lightly-contextual embedding for fast first-pass retrieval, a heavier contextual model for reranking a small candidate set.

---

## Build it from scratch

```python
# untested sketch — minimal skip-gram with negative sampling, enough to see the mechanism;
# gensim's Word2Vec is the reference production implementation to read next
import numpy as np
from collections import Counter

def build_vocab(tokenized_corpus: list[list[str]], min_count: int = 5):
    counts = Counter(w for doc in tokenized_corpus for w in doc)
    vocab = {w: i for i, (w, c) in enumerate(counts.items()) if c >= min_count}
    freqs = np.array([counts[w] for w in vocab], dtype=np.float64)
    noise_dist = freqs ** 0.75
    noise_dist /= noise_dist.sum()               # the 3/4-power negative-sampling distribution
    return vocab, noise_dist

def generate_pairs(tokenized_corpus, vocab, window=5):
    for doc in tokenized_corpus:
        ids = [vocab[w] for w in doc if w in vocab]
        for i, center in enumerate(ids):
            lo, hi = max(0, i - window), min(len(ids), i + window + 1)
            for j in range(lo, hi):
                if j != i:
                    yield center, ids[j]

def sigmoid(x):
    return 1.0 / (1.0 + np.exp(-x))

def train_sgns(pairs, vocab_size, dim=100, k=5, noise_dist=None, lr=0.025, epochs=1):
    W_in = (np.random.rand(vocab_size, dim) - 0.5) / dim     # center-word embeddings
    W_out = np.zeros((vocab_size, dim))                       # context-word embeddings
    for _ in range(epochs):
        for center, context in pairs:
            v_in = W_in[center]

            # positive example: push real pair's dot product up
            score = sigmoid(np.dot(v_in, W_out[context]))
            grad = lr * (1 - score)
            W_out[context] += grad * v_in
            update_in = grad * W_out[context]

            # k negative examples: push fake pairs' dot product down
            negatives = np.random.choice(vocab_size, size=k, p=noise_dist)
            for neg in negatives:
                score = sigmoid(np.dot(v_in, W_out[neg]))
                grad = lr * (0 - score)
                W_out[neg] += grad * v_in
                update_in += grad * W_out[neg]

            W_in[center] += update_in
    return W_in                                                # the embeddings you actually keep
```

The three things a real implementation adds that this sketch skips: subsampling of frequent words (Word2Vec discards very common words like "the" with a probability proportional to their frequency, since they contribute little useful signal per occurrence and slow training), a proper learning-rate schedule (linear decay over training), and vectorized/batched negative sampling instead of a Python loop — `gensim` and the original C implementation both use these; read `gensim.models.Word2Vec`'s source next.

---

## How it's done in production

**gensim** — the reference Python implementation for training and serving Word2Vec, FastText, and Doc2Vec; still the standard tool when you need to train static embeddings on a custom corpus rather than use a pretrained set. **fastText (Facebook's C++/Python library)** — the reference fastText implementation, including pretrained vectors for 157 languages and a supervised text-classification mode built directly on the same subword machinery. **Pretrained GloVe vectors** (Stanford, trained on Common Crawl / Wikipedia / Twitter) — still widely downloaded as a fixed starting point rather than trained from scratch, since re-deriving general-domain word vectors rarely beats the publicly available ones unless your corpus is highly domain-specific. **Sentence-transformers / OpenAI / Voyage / Cohere embedding APIs** — the contextual side of this comparison, covered in the RAG track's embedding-choice module; production systems needing semantic search over full documents or queries use these, not static word vectors. **item2vec / prod2vec** — the direct commercial descendant of Word2Vec's architecture applied to non-text sequences (product view sequences, click sequences), a technique used across recommendation and personalization systems including item embeddings from browsing or booking sequences, directly relevant to a marketing-content team working on personalization and cold-start.

| Symptom | Cause | Fix |
|---|---|---|
| Similarity search returns semantically wrong neighbors for a polysemous term | Static embedding conflates multiple senses of a word into one vector | Move the affected step to a contextual embedding, or add sense disambiguation upstream (context-aware retrieval, not a fixed lookup) |
| New product/brand names get no embedding or a poor-quality one | Word2Vec/GloVe have no representation for out-of-vocabulary words | Switch to fastText, which composes a vector from character n-grams even for unseen words |
| Training a Word2Vec model on a large corpus is far slower than expected | Full softmax accidentally left enabled instead of negative sampling or hierarchical softmax | Verify the training config explicitly uses negative sampling (`sg=1, hs=0` in gensim) with a reasonable `k` (5-20) |
| Embedding-based search is fast in dev, too slow in production at scale | Recomputing embeddings per request instead of using precomputed static lookups where context doesn't matter | Precompute and cache static embeddings for anything that doesn't need per-request context sensitivity; reserve live inference for the contextual layer only |
| Nearest-neighbor results degrade after retraining embeddings from scratch | Embedding spaces from separate training runs are not aligned — vector directions are arbitrary per run, only relative geometry within one run is meaningful | Never mix vectors from different training runs in the same index; if updating, retrain fully and reindex, or use an alignment technique (Procrustes) if partial compatibility is required |
| fastText model uses far more memory/disk than a Word2Vec model of the same dimension | The character n-gram vocabulary is much larger than the word vocabulary, and each word's vector is a sum over multiple n-gram vectors stored separately | Trade off n-gram range and bucket size (`minn`/`maxn`, hashing bucket count) against memory budget; fastText's `-bucket` hashing parameter bounds n-gram table size similarly to the hashing trick in classical NLP |

---

## Tradeoffs & when NOT to use it

- **Don't use static embeddings for anything where word sense genuinely varies by context and that variation matters to the task.** Sentiment analysis on sarcasm-heavy text, coreference resolution, and any task sensitive to negation or scope are all cases where a fixed vector per word is a structural ceiling on accuracy no amount of data fixes.
- **Don't use plain Word2Vec/GloVe on a corpus with heavy misspellings, slang, or morphological richness (agglutinative languages, hashtags, product-name variants) — use fastText.** The OOV gap is not a minor edge case in marketing/social content; it's a large fraction of real traffic.
- **Don't retrain embeddings from scratch when a domain-appropriate pretrained set exists and your corpus is small.** Training stable, high-quality embeddings needs a genuinely large corpus (the original Word2Vec paper trained on ~1.6 billion words); a small domain-specific corpus (tens of thousands of documents) will produce noisy, unstable vectors, and fine-tuning or simply using pretrained general vectors is usually better.
- **Don't average word embeddings into a sentence/document vector and expect it to compete with a proper sentence embedding model for semantic search.** Naive averaging destroys word order and disproportionately reflects the most frequent words' directions; if you need document-level semantic similarity, use a model trained for that objective (Sentence-BERT and successors), not a mean-pooled Word2Vec.
- **Don't use contextual embeddings by default without checking the latency/cost budget.** The senior mistake in the other direction is reflexively reaching for a transformer forward pass in a system that never needed context sensitivity in the first place — a real, measurable cost paid for accuracy the task doesn't use.

---

## Interview questions

### Q1 — Derive the skip-gram with negative sampling objective from the full softmax.
**Testing:** whether you can actually derive it, not recite the name.
**Answer:** Full softmax defines `p(w_O|w_I) = exp(v'_{w_O}·v_{w_I}) / Σ_w exp(v'_w·v_{w_I})`, which requires summing over the entire vocabulary per training example — infeasible at scale. Negative sampling reframes the problem as binary classification: is `(w_I, w_O)` a real pair or one of `k` randomly sampled fake pairs? The objective becomes `log σ(v'_{w_O}·v_{w_I}) + Σ_{i=1}^{k} E_{w_i~P_n(w)}[log σ(−v'_{w_i}·v_{w_I})]`, turning an `O(V)` computation into `O(k)`.
**Follow-up trap:** *"Why the 3/4 power on the noise distribution?"* — raising unigram frequency to the 0.75 power dampens how dominant extremely frequent words are among the negative samples while still oversampling them relative to uniform; it's an empirical finding (Mikolov et al.), not derived from first principles, and saying so honestly is correct.

### Q2 — CBOW or skip-gram: when would you pick each?
**Answer:** CBOW predicts the center word from the averaged context vector — faster to train (one prediction per window) and tends to do better on frequent words since averaging smooths noise. Skip-gram predicts each context word individually from the center — slower, but treats rare words as independent training signals rather than diluting them into an average, so it typically wins on smaller datasets and rare-word quality.
**Follow-up trap:** *"Does the choice matter much in practice at large scale?"* — less than people expect; with enough data both converge to similar quality, and the practical choice is often driven by training speed constraints rather than a large accuracy gap.

### Q3 — Explain GloVe's objective and why it uses a weighting function `f(X_ij)`.
**Answer:** GloVe minimizes `Σ f(X_ij) (w_i·w̃_j + b_i + b̃_j − log X_ij)²`, fitting the dot product of two word vectors to the log of their co-occurrence count. `f(x) = (x/x_max)^α` for `x < x_max`, else 1 — this prevents extremely frequent co-occurrences from dominating the loss (they'd otherwise contribute enormous squared-error gradients) while still giving zero weight to co-occurrences that never happened, avoiding `log(0)`.
**Follow-up trap:** *"Why does GloVe use log co-occurrence counts specifically, not raw counts?"* — because ratios of co-occurrence probabilities, not raw probabilities, are what carries meaning (the ice/steam/solid/gas argument from the original paper), and fitting dot products to log-counts is what makes vector differences correspond to log-probability ratios, which is what gives GloVe vectors their analogy-arithmetic property.

### Q4 — What did Levy & Goldberg (2014) prove about skip-gram with negative sampling, and why does it matter?
**Answer:** SGNS implicitly factorizes a word-context PMI matrix, shifted by `−log(k)`: `v_{w_I}·v'_{w_O} ≈ PMI(w_I, w_O) − log(k)`. It matters because it shows Word2Vec and GloVe are not unrelated algorithms — one performs implicit factorization via gradient descent on local prediction, the other performs explicit factorization of global counts — and it explains why increasing `k` (more negative samples) behaves like a stronger PMI shift, effectively demanding higher co-occurrence before two words are pulled together.
**Follow-up trap:** *"Does that mean you could just factorize the PMI matrix directly instead of training Word2Vec?"* — yes, and people have (explicit PMI-matrix SVD is a real alternative); it typically needs comparable or more memory to hold the matrix explicitly and doesn't stream over a corpus the way SGNS does, which is why the online, prediction-based formulation won as the practical training method despite the equivalence.

### Q5 — How does fastText produce a vector for a word it never saw during training?
**Answer:** Every word is represented as a bag of character n-grams (typically length 3-6) plus a whole-word token, and the word's vector is the sum of its n-gram vectors. An unseen word decomposes into n-grams that likely were seen (as substrings of other training words), so summing their trained vectors produces a usable, if imperfect, representation — Word2Vec and GloVe have no equivalent mechanism and simply have no vector for an unseen word.
**Follow-up trap:** *"Does this work for a completely novel string with unfamiliar n-grams too?"* — no, it degrades gracefully rather than perfectly; if none of a word's n-grams appeared in training (rare, but possible for truly novel strings or a different script), fastText falls back to essentially random/uninformative subword vectors, so it's a mitigation, not a complete solution to OOV.

### Q6 — Why can't a static embedding represent polysemy, structurally?
**Answer:** Training assigns exactly one vector per word type by design — the training objective aggregates evidence from every context the word appears in during training into a single point in vector space, which necessarily averages across senses rather than separating them. There is no mechanism in the architecture to condition the output on which sentence you're currently in, because the vector is computed once, offline, and looked up, not computed at inference time.
**Follow-up trap:** *"Could you cluster a word's contexts and assign multiple vectors per sense?"* — yes, and this was tried (multi-sense/multi-prototype embeddings, pre-dating contextual models) but never displaced static single-vector embeddings in practice, because choosing the number of senses per word and disambiguating at inference time turned out to be almost as hard as the contextual-embedding problem it was trying to avoid, without the benefit of end-to-end learning.

### Q7 — When would you choose a static embedding over a contextual one in a real system?
**Testing:** the senior tradeoff signal for this module.
**Answer:** When the task doesn't need context sensitivity and the latency/cost budget is tight — real-time lookups at high QPS, on-device/edge inference, coarse topical similarity or query expansion, or as input to a simple linear classifier where interpretability matters. A static lookup is microseconds and free after training; a contextual embedding needs a forward pass, commonly single-digit to tens of milliseconds, on every request.
**Follow-up trap:** *"Your system needs both cheap first-pass filtering and high accuracy. What do you do?"* — a two-stage pipeline: static (or lightweight) embeddings for fast candidate generation over the full corpus, contextual embeddings for reranking a small shortlist — the standard retrieve-then-rerank pattern, applied to the embedding-cost axis rather than just the retrieval-accuracy axis.

### Q8 — What's the practical difference between training Word2Vec and training GloVe on the same corpus?
**Answer:** Word2Vec is online/streaming — it processes the corpus as a sequence of local context windows and updates incrementally, never materializing a global matrix. GloVe is batch — it first builds the full word-word co-occurrence matrix (a real memory cost, scaling with vocabulary size squared in the worst case, though sparse in practice), then factorizes it. In practice, on standard similarity/analogy benchmarks the two produce comparable quality, so the choice is usually about training infrastructure (can you stream vs. do you have memory for the co-occurrence matrix) rather than a measured accuracy winner.
**Follow-up trap:** *"So there's no reason to prefer one over the other?"* — GloVe's global-statistics framing has a real advantage on rare-word pairs that co-occur infrequently but consistently across the whole corpus, since it sees the aggregate count directly rather than accumulating gradient signal window by window; this is a real, if usually small, distinction worth naming rather than claiming total equivalence.

### Q9 — Your team wants to use average word embeddings as document vectors for a search feature. What goes wrong?
**Answer:** Mean-pooling destroys word order entirely (same failure mode as bag-of-words) and the average is disproportionately influenced by the most frequent words in the document, which are often the least discriminative ones — the same problem raw TF without IDF weighting has. It also can't distinguish "the hotel was not clean" from "the hotel was clean," since negation scope is lost in an unordered average.
**Follow-up trap:** *"How would you fix it while staying in the static-embedding world?"* — weight the average by TF-IDF instead of uniform mean (SIF/smooth inverse frequency weighting is the well-known refinement here), which at least down-weights frequent, low-information words; but for genuine sentence-level semantics, the honest answer is that you should move to a model trained specifically for sentence embeddings rather than patch averaging further.

### Q10 — What is subsampling of frequent words in Word2Vec, and why is it needed?
**Answer:** Extremely frequent words ("the," "a," "of") appear in so many context windows that they contribute a large volume of low-information training examples and slow training without proportionally improving embedding quality. Word2Vec discards each word during training with a probability that increases with its frequency (a formula involving a threshold parameter, commonly around `1e-3` to `1e-5`), which both speeds up training and, empirically, improves the quality of rarer word vectors by giving them relatively more influence per pass over the corpus.
**Follow-up trap:** *"Isn't this redundant with negative sampling's 3/4-power noise distribution?"* — no, they solve different problems: subsampling controls which *positive* examples get used during training at all; the noise distribution controls which words get sampled as *negative* examples. Both dampen the influence of frequent words, but at different points in the pipeline, and removing one doesn't substitute for the other.

### Q11 — A marketing personalization team wants to embed user browsing sequences (not text) to power recommendations. Is Word2Vec applicable?
**Answer:** Yes — this is exactly the item2vec/prod2vec pattern: treat each user's sequence of viewed or booked items as a "sentence" and each item as a "word," then train skip-gram with negative sampling over these sequences the same way you would over natural language. Items that co-occur in similar browsing contexts end up with similar vectors, which is directly usable for similarity-based recommendation and cold-start-adjacent tasks (an item with few interactions but items frequently co-viewed with it still gets a meaningful vector via the co-occurrence signal).
**Follow-up trap:** *"How does this help with true cold start, where an item has zero interactions?"* — it doesn't, directly — an item with literally no co-occurrence data gets no trained vector, same limitation as Word2Vec's OOV problem for text. The fix mirrors fastText's: compose an initial vector from item metadata/content features (category, price tier, description embedding) rather than relying purely on interaction co-occurrence, or fall back to a content-based similarity model until enough interaction data accumulates.

### Q12 — What's the vector arithmetic property ("king − man + woman ≈ queen") actually telling you about the embedding space, and does it hold reliably?
**Answer:** It suggests that certain semantic relationships are encoded as roughly consistent directions/offsets in the embedding space (a "gender" direction, a "capital city" direction), which is a genuinely useful property for tasks like analogy completion, and it's one of the most publicly memorable results from the original Word2Vec paper. It does not hold reliably or precisely for most word pairs — it works well for the curated analogy benchmarks used to showcase it and degrades noticeably outside that regime, so citing it as evidence embeddings "understand meaning" overstates what's actually a rough linear regularity that emerges from the training objective, not a designed feature.
**Follow-up trap:** *"Do contextual embeddings preserve this property?"* — not in the same clean, single-vector sense, since a contextual model doesn't produce one fixed vector per word to do arithmetic on; you can extract fixed embeddings from a contextual model (e.g., averaging over many contexts) and test similar arithmetic, but it's a secondary property of the extracted representation, not a core design goal the way it was for Word2Vec.

### Q13 — How would you detect that your embedding-based similarity search has degraded after a routine retraining?
**Answer:** Two failure modes to check separately: quality degradation (the new embeddings are genuinely worse — evaluate on a held-out word-similarity or analogy benchmark, or better, a task-specific eval like click-through on search results) and alignment breakage (the new embedding space's geometry isn't comparable to the old one even if individually valid, because embedding spaces from separate training runs have arbitrary orientation — only relative geometry within a single run is meaningful). If you mixed old and new vectors in the same index without full reindexing, you'd see nonsensical nearest neighbors even though each individual training run was fine.
**Follow-up trap:** *"How do you avoid downtime during a full reindex?"* — build the new index in parallel (blue-green), validate it against the eval set and a small live-traffic shadow test, then cut over atomically; never serve a mixed index where some vectors came from the old training run and some from the new one.

### Q14 — Static or contextual embeddings for a real-time query-autocomplete feature at high QPS?
**Testing:** applying the tradeoff to a concrete latency-sensitive scenario.
**Answer:** Static, almost certainly — autocomplete needs sub-10ms responses at very high QPS, per-keystroke in the worst case, and the semantic distinctions autocomplete needs (broad topical/lexical similarity to suggest completions) rarely depend on fine-grained context disambiguation. A precomputed static embedding index with approximate nearest-neighbor search meets the latency bar; a contextual forward pass per keystroke does not, at reasonable infrastructure cost.
**Follow-up trap:** *"What if query intent genuinely depends on context, e.g. prior search history?"* — that's a legitimate reason to add a contextual or session-aware layer, but the right architecture is still likely a fast static/ANN first pass for candidate generation, with any context-dependent reranking applied only to the small shortlist — not contextual inference on the full candidate space at request time.

### Q15 — Design an embedding strategy for a content platform that needs both fast bulk content tagging (millions of documents, batch) and high-accuracy real-time search (low QPS, quality-critical).
**Testing:** synthesis across the whole cost/accuracy spectrum this module covers.
**Answer:** These are different points on the latency/cost/accuracy curve and deserve different tools. Bulk tagging is offline and throughput-bound, not latency-bound, so it can afford contextual embeddings run as a batch job (no per-request SLA) for accuracy, or a lighter fastText/static-embedding-plus-linear-classifier pipeline if the accuracy is sufficient and infra cost dominates the decision — measure both before committing. Real-time search is low-QPS but quality-critical, so it can afford a contextual embedding model per query (the query side of the pipeline is cheap because it's one embedding per search, not per document) combined with precomputed document embeddings (computed once offline, contextual or static depending on how much the accuracy gain matters for that corpus) — the classic asymmetric-cost pattern where the expensive side of a bi-encoder is precomputed and the cheap side runs live.
**Follow-up trap:** *"What changes if bulk tagging volume grows 100x overnight (a new content partner)?"* — that shifts the batch job from "affordable to run contextual" to "reconsider the cost model" — re-run the cost-per-document math at the new volume before assuming the existing architecture still holds; this is the same lesson as the vector-index-internals module's "recall drops after 10x growth" failure mode, applied to embedding cost instead of search recall.

---

## Red flags that fail you

- Describing Word2Vec's objective as "predict nearby words" without being able to write the negative sampling loss.
- Not knowing why full softmax is infeasible at vocabulary scale, or claiming negative sampling is "just an optimization trick" rather than naming what it approximates.
- Confusing GloVe's count-based factorization with Word2Vec's prediction-based training, or claiming they're the same algorithm.
- Not knowing fastText's mechanism for OOV words (character n-gram summation) beyond "it handles unknown words somehow."
- Claiming static embeddings "understand" polysemy, or that contextual embeddings have no real-world use case where static wins.
- Averaging word embeddings into a document vector and presenting it as competitive with a real sentence-embedding model without acknowledging the limitation.
- Reaching for a transformer forward pass by default without considering the latency/cost budget of the system.
- Mixing embedding vectors from two different training runs in the same similarity index.

---

## Cheat card

```
SKIP-GRAM (Mikolov 2013)   predict context from center word
  full softmax: O(V) per example — infeasible at scale
  negative sampling: log σ(v'_wO · v_wI) + Σ_{i=1}^k E[log σ(−v'_wi · v_wI)]
  noise dist P_n(w) ∝ count(w)^0.75  (3/4 power — empirical, dampens frequent-word dominance)
  k = 5-20 (small data), 2-5 (large data)
CBOW   predict center from AVERAGED context. Faster, better on frequent words.
SKIP-GRAM  better on rare words / small datasets (no averaging dilution).

LEVY & GOLDBERG (2014)   SGNS implicitly factorizes PMI matrix shifted by −log(k):
                         v_wI · v'_wO ≈ PMI(wI,wO) − log(k)   [theoretical bridge to GloVe]

GLOVE (Pennington 2014)   count-based, batch, factorizes global co-occurrence matrix X
  J = Σ f(X_ij)(w_i·w̃_j + b_i + b̃_j − log X_ij)²
  f(x) = (x/x_max)^α if x<x_max else 1;  x_max=100, α=0.75
  ratios of co-occurrence probs encode meaning better than raw probs (ice/steam/solid/gas)

FASTTEXT (Bojanowski 2017)   word vector = SUM of character n-gram vectors (n=3-6) + whole word
  fixes OOV (unseen word → sum of its known n-grams) and morphology (shared substrings)
  larger model (bigger n-gram vocab), slower lookup (sum not single index)

WHY CONTEXTUAL WON   static = ONE vector/word type, frozen at train time — can't represent polysemy
  ELMo (2018): BiLSTM hidden states per token.  BERT (2018): transformer, MLM — became the default.
  structural limitation, not fixable with more data on the static side.

STATIC STILL WINS WHEN   latency (μs lookup vs ms forward pass) · cost (precompute once vs pay
  per request) · interpretability (fixed, auditable nearest neighbors) · edge/on-device ·
  item2vec/prod2vec over non-text interaction sequences (cold-start-adjacent, not true cold start)

DON'T   average word vectors and call it a document embedding without TF-IDF/SIF weighting —
        still loses order and negation. Don't mix vectors from separate training runs (unaligned
        geometry). Don't retrain from scratch on a small corpus — use pretrained + fine-tune.
```

## Sources

- [Distributed Representations of Words and Phrases and their Compositionality — Mikolov et al., 2013](https://arxiv.org/abs/1310.4546) — accessed 2026-08-02
- [word2vec Explained: Deriving Mikolov et al.'s Negative-Sampling Word-Embedding Method — Goldberg & Levy, 2014](https://ar5iv.labs.arxiv.org/html/1402.3722) — accessed 2026-08-02
- [Neural Word Embedding as Implicit Matrix Factorization — Levy & Goldberg, 2014 (NeurIPS)](https://papers.nips.cc/paper_files/paper/2014/hash/feab05aa91085b7a8012516bc3533958-Abstract.html) — accessed 2026-08-02
- [GloVe: Global Vectors for Word Representation — Pennington, Socher, Manning, 2014](https://nlp.stanford.edu/pubs/glove.pdf) — accessed 2026-08-02
- [Enriching Word Vectors with Subword Information — Bojanowski et al., 2017 (fastText)](https://arxiv.org/abs/1607.04606) — accessed 2026-08-02
- [Deep contextualized word representations — Peters et al., 2018 (ELMo)](https://arxiv.org/abs/1802.05365) — accessed 2026-08-02
- [BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding — Devlin et al., 2018](https://arxiv.org/abs/1810.04805) — accessed 2026-08-02
- [Obtaining Better Static Word Embeddings Using Contextual Embedding Models, 2021 (static vs. contextual cost tradeoffs)](https://arxiv.org/abs/2106.04302) — accessed 2026-08-02
- [Item2Vec: Neural Item Embedding for Collaborative Filtering](https://arxiv.org/abs/1603.04259) — accessed 2026-08-02
- [Machine Learning Scientist III, NLP at Expedia Group — WORK180 (Bayesian, LDA, NER, Random Forests requirements)](https://work180.com/en-us/for-women/employer/expedia/job/458598/machine-learning-scientist-iii-nlp) — accessed 2026-08-02

## Changelog
- 2026-08-02 — created
