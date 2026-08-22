# Named Entity Recognition: CRF, BiLSTM-CRF, Transformer NER, Custom Entities, Eval

> **Track:** T32 Applied NLP & Marketing ML · **Time:** 2.5h · **Prereqs:** T32-nlp-classical, T32-word-embeddings · **Updated:** 2026-08-02
> **Module id:** `T32-ner` · **Tags:** nlp, critical

## The 30-second version

NER is sequence labeling: assign every token a tag that says whether it starts, continues, or falls outside a named entity span. Linear-chain CRFs model this as a globally normalized scoring function over the whole tag sequence, so the model can learn that "I-PER can't follow B-LOC" instead of tagging each token independently; BiLSTM-CRF adds a neural feature extractor (word plus character-level representations, run through a bidirectional LSTM) underneath the same CRF layer, and was the dominant architecture from roughly 2016 through the transformer era. Transformer NER (fine-tuned BERT-style token classification) replaced hand-built and BiLSTM features with contextual embeddings and mostly dropped the CRF layer, because a strong enough encoder makes most of the illegal-sequence errors a CRF exists to prevent rare enough not to matter — though CRF-on-top-of-transformer is still a legitimate choice for tightly constrained, high-precision production tags. Tagging scheme matters more than people think: BIO (Begin/Inside/Outside) is the default because it's compact and universally supported, BIOES/BILOU (adding explicit End/Single tags) gives the model more boundary signal and helps most on longer entities and adjacent-entity disambiguation. The evaluation trap that catches candidates cold is scoring at the token level instead of the entity level — a model can get every individual token's tag right in isolation while still getting zero credit under entity-level F1 if a single boundary token in a multi-token span is wrong, because a partial match is a miss.

## Why this gets asked

Whoever wrote this question watched a "99% accurate" NER model ship and then fail in production, because 99% token accuracy on a corpus that's 90%+ "O" (outside any entity) tags is a nearly meaningless number — a model that predicts "O" for everything scores 90%. They want to know you'd catch that before it shipped, that you understand entity-level F1 is the real metric, and that you've thought about the unglamorous parts: what entity schema to define, how to get enough labeled data without manually annotating a hundred thousand sentences, and what a specific travel-domain entity extraction pipeline (destinations, dates, room types, loyalty IDs) actually looks like end to end.

---

## Lineage: past → present → future

**What came before.** Early NER (MUC-6, 1995, the shared task that established the "PER/ORG/LOC" convention still used today) was rule-based: hand-built gazetteers (lists of known person/organization/location names) plus regex and capitalization heuristics. This worked precisely as well as the gazetteer's coverage and broke on anything novel — a new company name, an entity in a different capitalization convention, an entity type the rule author didn't anticipate — and maintaining the rule set against a growing, shifting entity space became the actual bottleneck. Statistical sequence models (HMMs, then Maximum Entropy Markov Models) tried to learn this from data instead of rules but suffered the "label bias problem" — MEMMs normalize transition probabilities locally at each step, which structurally biases the model toward states with fewer outgoing transitions regardless of the observation, a subtle but real pathology.

**Where it stands now.** Linear-chain CRFs (Lafferty, McCallum, Pereira, 2001) fixed the label bias problem by normalizing globally over the whole sequence instead of locally per-transition, and were the production standard through the mid-2010s, typically fed hand-engineered features (word shape, prefix/suffix, gazetteer membership, POS tag). BiLSTM-CRF (Huang, Xu, Yu, 2015; Lample et al., 2016) replaced hand-engineered features with learned ones — a BiLSTM reading the sentence in both directions produces a contextual feature vector per token, feeding the same CRF layer for structured decoding — and pushed English NER benchmarks (CoNLL-2003) into the low-to-mid 90s F1 for the first time without hand-crafted features. Transformer-based NER (BERT fine-tuned as a token-classification head, 2018 onward) then pushed further, mostly without a CRF layer at all, because a sufficiently strong contextual encoder rarely produces the illegal tag transitions (an "I-PER" token immediately after an "O" token, for instance) that a CRF's transition matrix exists to forbid — current state-of-the-art English NER sits around 93-94 F1 on CoNLL-2003, and the CRF layer's marginal contribution on top of a strong transformer is small enough that many production systems drop it for simplicity. The live disagreement is whether the CRF layer is still worth the added complexity: teams running high-precision, narrowly-scoped extraction (specific structured fields like flight numbers or loyalty IDs) often keep it because it provides a hard constraint against nonsensical output the transformer alone doesn't reliably avoid, while teams doing broad, general-domain entity extraction increasingly skip it.

**Where it's heading.** High confidence: LLM-based zero-shot and few-shot entity extraction (prompt an LLM with the entity schema and let it return structured output) is eating the long tail of low-volume, rapidly-changing entity schemas, because standing up a fine-tuned NER model for a new entity type with limited labeled data is real engineering cost an LLM call sidesteps entirely. Moderate confidence: fine-tuned transformer NER keeps its seat wherever throughput or cost rules out an LLM call per document, and wherever the entity schema is stable enough to amortize the fine-tuning cost — this describes most high-volume production content pipelines, including a marketing content platform tagging entities across millions of listings. Speculative: some argue structured-output-constrained LLM extraction will eventually match fine-tuned NER's cost profile as inference gets cheaper and batching improves — this is directionally plausible but not true today at the throughput (thousands of documents/second) many content pipelines actually need, and asserting it's already solved is a real gap between what's published and what's deployed.

---

## Mental model

```
"Book a flight from Seattle to Denver on March 3rd"

tokens:    Book   a   flight  from   Seattle   to   Denver   on   March   3rd
BIO tags:   O     O     O      O      B-ORIG    O    B-DEST   O    B-DATE  I-DATE

BIOES tags: O     O     O      O      S-ORIG    O    S-DEST   O    B-DATE  E-DATE
            (S = Single-token entity, E = End of multi-token entity — explicit boundary signal)

                        ┌─────────────────────────────────┐
    words/chars ──▶ embed ──▶ BiLSTM (context both directions) ──▶ per-token scores
                        └─────────────────────────────────┘
                                       │
                                       ▼
                    CRF layer: score the WHOLE tag sequence jointly,
                    learn transition penalties (e.g. I-DATE can't follow O directly)
                                       │
                                       ▼
                         Viterbi decode: best legal tag sequence
```

The one thing to internalize: NER is not per-token classification wearing a sequence-model costume. The entire reason CRFs and BiLSTM-CRF exist is that tags are not independent — knowing the previous tag changes what the next tag can legally be — and any evaluation or architecture that treats tokens as i.i.d. is throwing away the one structural fact that makes this task different from ordinary classification.

---

## How it actually works

### Linear-chain CRF, derived

A linear-chain CRF models the conditional probability of a tag sequence `y = (y_1, ..., y_n)` given an observation sequence `x = (x_1, ..., x_n)` directly, rather than modeling `P(x, y)` jointly like an HMM does. The score of a full sequence is a sum of feature functions:

```
score(x, y) = Σ_{i=1}^{n} [ Σ_k λ_k * f_k(y_{i-1}, y_i, x, i) ]

P(y | x) = exp(score(x, y)) / Z(x)

Z(x) = Σ_{y'} exp(score(x, y'))          # partition function: sum over ALL possible tag sequences
```

`f_k` are feature functions (can depend on the current and previous tag, the full observation sequence, and the current position — this is the key generalization over an HMM, which restricts itself to `P(word|tag)` and `P(tag|prev_tag)` separately), `λ_k` are learned weights. The **partition function `Z(x)`** is what makes this a *globally* normalized model — it sums over every possible tag sequence, not just normalizing each transition step locally the way an MEMM does, which is precisely what fixes the label bias problem: no state is structurally penalized just for having fewer outgoing transitions, because normalization happens once, over the whole sequence.

Computing `Z(x)` naively requires summing over `T^n` possible tag sequences (`T` tags, `n` tokens) — exponential. The **forward-backward algorithm** computes it in `O(n * T^2)` via dynamic programming, exploiting the fact that the score decomposes into a sum of local terms that only depend on adjacent tag pairs. Training maximizes the conditional log-likelihood via gradient ascent, and the gradient of the log-likelihood with respect to each feature weight has a closed form in terms of the forward-backward quantities (expected feature counts under the model, minus observed feature counts in the training data) — the same forward-backward machinery used for inference is reused for training.

**Decoding** (finding the single best tag sequence, not summing over all of them) uses the **Viterbi algorithm**, also `O(n * T^2)`: a dynamic program that tracks, for each position and each tag, the best-scoring partial sequence ending in that tag, and backtracks at the end to recover the full best sequence. This is where the CRF's transition weights do their real work in production — a CRF with a strongly negative learned weight for the `(O, I-PER)` transition will simply never output that illegal sequence, because Viterbi is optimizing globally, not token by token.

### BiLSTM-CRF

The CRF's feature functions `f_k` in the classical (pre-neural) formulation were hand-engineered: word identity, word shape (capitalization pattern), prefix/suffix character n-grams, POS tag, gazetteer membership. BiLSTM-CRF (Lample et al., 2016) replaces this feature engineering with a learned representation: run a bidirectional LSTM over the sentence's word embeddings (concatenated with a character-level representation — typically a small CNN or LSTM over the characters of each word, which captures morphological and spelling signal a word embedding alone misses, especially useful for out-of-vocabulary or misspelled tokens) to produce a contextual vector per token, then feed a linear projection of that vector as the emission score into the same CRF scoring and decoding machinery described above. The architecture is genuinely two separable pieces — a neural feature extractor (BiLSTM plus optional char-CNN) and a structured output layer (CRF) — and the CRF layer's job doesn't change from the classical formulation, it just receives learned features instead of hand-built ones. This is why BiLSTM-CRF pushed CoNLL-2003 English NER F1 into the low-to-mid 90s without hand-crafted gazetteers: the character-level component alone recovers a meaningful fraction of what gazetteers used to provide, because it learns that capitalized, suffix-`-ton`-ending tokens are plausibly place names, without anyone writing that rule.

### Transformer NER

Fine-tuned transformer NER (BERT and successors, used as a token-classification model) replaces the BiLSTM feature extractor with a pretrained transformer encoder, fine-tuning a linear classification head on top of each token's final hidden state. Two production-specific mechanics matter here that don't come up in the classical formulation:

1. **Subword alignment.** BERT-style tokenizers split words into subwords (module 1's BPE/WordPiece), so a single word like "Copenhagen" might become three subword tokens, but the training label is defined per *word*, not per subword piece. The standard convention: assign the word's label to its first subword token and either mask the remaining subwords from the loss (the common choice) or propagate the same label with an `I-` prefix if the entity continues. Getting this wrong — training on subword-token-level labels that don't align to word boundaries — silently corrupts the training signal and is one of the most common real bugs in a from-scratch transformer NER implementation.
2. **Whether to keep the CRF layer.** Fine-tuned transformers rarely output the illegal tag sequences (an `I-PER` immediately after an unrelated `O`) that a CRF's transition matrix is designed to forbid, because the encoder's contextual representations already encode enough sequential structure implicitly. Many production systems drop the CRF layer entirely for a simple softmax per token, trading a small amount of structural guarantee for a simpler model and faster training. Systems needing a hard guarantee against illegal output for downstream structured use (a flight-booking pipeline that cannot tolerate a malformed date-entity boundary) still add a CRF layer on top of the transformer's contextual embeddings, getting both the encoder's representational power and the CRF's global decoding constraint.

### BIO vs. BIOES/BILOU

**BIO** tags each token as `B-TYPE` (beginning of an entity), `I-TYPE` (inside/continuation of an entity), or `O` (outside any entity) — for `k` entity types this needs `2k + 1` tags. It's compact, universally supported by every NER toolkit and dataset, and works well in practice. **BIOES** (Begin/Inside/Outside/End/Single) adds an explicit `E-TYPE` tag for the last token of a multi-token entity and an `S-TYPE` tag for single-token entities, needing `4k + 1` tags. The added signal — explicitly marking both where an entity starts *and* where it ends, rather than inferring the end only implicitly from the next tag not being `I-TYPE` — measurably helps boundary detection on longer entities and on sequences with adjacent entities of the same type back to back (where BIO's `I-TYPE, B-TYPE` transition can be ambiguous to learn cleanly), at the cost of a larger output vocabulary (more label confusion surface) and lower `O`-tag frequency skew. The practical tradeoff: BIOES is a legitimate, often modest F1 improvement, particularly for longer entities, but the gain is not universal and BIO's simplicity (fewer labels, less tooling friction, the default in almost every off-the-shelf dataset) makes it the right starting default; only switch to BIOES if you've measured a concrete gain on your own data.

### Custom entity types

Defining a custom entity schema is a design decision with real downstream cost, not a free label to add. Three concrete considerations: **granularity** (is "hotel amenity" one entity type, or do "pool," "gym," "parking" need to be separate types because downstream logic treats them differently — finer granularity needs more labeled examples per type to reach usable accuracy); **overlap and nesting** (can entities overlap or nest — "Seattle" inside "Seattle-Tacoma International Airport" — standard BIO/BIOES tagging assumes flat, non-overlapping spans, and genuinely nested entities need either a separate nested-NER architecture, layered flat extraction passes, or a schema redesign that avoids the nesting); and **class imbalance across types** (a schema with one entity type appearing in 40% of examples and another in 0.5% needs either oversampling, type-specific evaluation thresholds, or accepting that the rare type will have wide confidence intervals on any F1 estimate from a modest test set).

### Active learning for annotation

NER labeling is expensive per example (a human must read the full sentence and mark every span, not just answer one classification question), which makes annotation budget the real production bottleneck far more often than model architecture. Active learning selects which unlabeled examples to send to annotators next, rather than labeling randomly, to maximize model improvement per labeled example. **Uncertainty sampling** — prioritize sentences the current model is least confident about — is the most common and empirically strongest simple strategy for NER; for a CRF or BiLSTM-CRF, uncertainty can be measured via the margin between the top-1 and top-2 Viterbi-decoded sequence scores, or via token-level entropy aggregated across the sentence. Published results in clinical NER annotation report uncertainty sampling reaching a target F-measure with roughly 66% fewer annotated sentences than random sampling — a large, real cost reduction, and the reason active learning is worth the extra pipeline complexity whenever annotation is the bottleneck (which, for a new or evolving entity schema, it almost always is). **Diversity sampling** (select examples that are dissimilar to what's already labeled, often via clustering sentence embeddings) complements uncertainty sampling by avoiding the failure mode where uncertainty sampling repeatedly selects near-duplicate hard examples from the same narrow region of the input distribution; hybrid strategies that switch between the two based on training progress are an active research area, not yet a single settled default.

### Evaluation: entity-level F1, not token-level

This is the single most consequential evaluation mistake to avoid. **Token-level accuracy or F1** scores each token's predicted tag independently against the gold tag — and because the vast majority of tokens in any real corpus are `O` (outside any entity), a model that predicts `O` for everything can score 85-95%+ token accuracy while extracting zero entities correctly. **Entity-level (span-level) F1** — computed by the standard `seqeval` library convention — instead requires the predicted span to match the gold span *exactly*: same start token, same end token, same entity type. A predicted span that's off by even one boundary token (predicting `[Seattle, to]` as the origin instead of just `[Seattle]`) counts as both a false positive (wrong span predicted) and a false negative (correct span missed) under strict exact-match entity-level scoring — there is no partial credit in the standard convention, which is a deliberately strict choice because a downstream system consuming a malformed entity boundary (a booking system extracting "Seattle to" as a city name) fails just as badly as if the entity were missed entirely.

---

## Build it from scratch

```python
# untested sketch — minimal linear-chain CRF forward algorithm and Viterbi decode,
# enough to see the DP structure; a real implementation trains with a proper
# optimizer and uses log-space arithmetic throughout for numerical stability
import numpy as np

def forward_log_Z(emissions: np.ndarray, transitions: np.ndarray) -> float:
    """emissions: (n_tokens, n_tags) unary scores. transitions: (n_tags, n_tags), transitions[i,j]
    = score of moving from tag i to tag j. Returns log(Z(x)) via the forward algorithm."""
    n_tokens, n_tags = emissions.shape
    alpha = emissions[0]                                    # log-space forward scores at t=0
    for t in range(1, n_tokens):
        # broadcast: alpha[i] + transitions[i,j] + emissions[t,j], logsumexp over i
        scores = alpha[:, None] + transitions + emissions[t][None, :]
        alpha = np.logaddexp.reduce(scores, axis=0)
    return np.logaddexp.reduce(alpha)                       # log(Z(x)) = logsumexp over final tags

def viterbi_decode(emissions: np.ndarray, transitions: np.ndarray) -> list[int]:
    """Returns the single best tag sequence (indices), not the full distribution."""
    n_tokens, n_tags = emissions.shape
    backpointers = np.zeros((n_tokens, n_tags), dtype=int)
    scores = emissions[0]
    for t in range(1, n_tokens):
        candidate = scores[:, None] + transitions            # (prev_tag, curr_tag)
        backpointers[t] = np.argmax(candidate, axis=0)
        scores = np.max(candidate, axis=0) + emissions[t]
    best_last = int(np.argmax(scores))
    path = [best_last]
    for t in range(n_tokens - 1, 0, -1):
        best_last = int(backpointers[t, best_last])
        path.append(best_last)
    return path[::-1]

def entity_level_f1(gold_spans: set[tuple], pred_spans: set[tuple]) -> tuple[float, float, float]:
    """spans as (start, end, type) tuples; exact match only, no partial credit."""
    tp = len(gold_spans & pred_spans)
    precision = tp / len(pred_spans) if pred_spans else 0.0
    recall = tp / len(gold_spans) if gold_spans else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return precision, recall, f1
```

The three things a real implementation adds that this sketch skips: log-space-stable `emissions`/`transitions` learned jointly with a neural feature extractor via backpropagation through the forward algorithm (not hand-set scores), a proper BIO/BIOES-constrained transition matrix (some transitions like `O → I-TYPE` should be masked to `-inf` rather than merely learned as unlikely, guaranteeing legality rather than just discouraging illegality), and batched, padded sequence handling for realistic training throughput. `pytorch-crf` and `flair`'s CRF implementation are the references to read next.

---

## How it's done in production

**spaCy** — ships pretrained NER pipelines per language and a training framework for custom entity types; the standard choice for teams that want production-grade NER without building the training loop themselves. **Hugging Face `transformers`** (`AutoModelForTokenClassification`) — the reference fine-tuning path for transformer NER, with the subword-alignment utilities built in (`tokenizer.word_ids()` maps subword tokens back to original word indices, directly solving the alignment mechanic described above). **Flair** — a research-and-production NER library known for strong BiLSTM-CRF-with-contextual-embeddings results and straightforward custom entity training. **AWS Comprehend / GCP Natural Language / Azure AI Language** — managed NER APIs with a fixed general-purpose entity set plus a custom-entity training option; the right choice when you don't want to own model training infrastructure and your entity set fits a standard schema, wrong when you need tight latency/cost control at very high volume or highly domain-specific entity types the managed service's custom-training UI doesn't handle well. **`seqeval`** — the reference Python library for entity-level (not token-level) precision/recall/F1, implementing the strict-match convention described above; if a production eval pipeline isn't using `seqeval` or an equivalent span-exact-match scorer, treat any reported F1 number with suspicion until you've checked which convention it used.

**Worked example — travel-domain entity schema**, directly relevant to a JD naming NER for marketing content: `ORIGIN`, `DESTINATION`, `TRAVEL_DATE`, `RETURN_DATE`, `AIRLINE`, `FLIGHT_NUMBER`, `HOTEL_NAME`, `ROOM_TYPE`, `PRICE`, `DURATION`, `LOYALTY_ID`, `AMENITY`. Concrete design choices this schema forces: `ORIGIN`/`DESTINATION` need disambiguation logic beyond the tag itself (a dependency parse or positional heuristic distinguishing "from Seattle to Denver" is often more reliable than the NER model alone, since NER tags a span's type but not its directional role); `PRICE` and `DURATION` are highly regular in surface form (currency symbols, digit patterns, unit words) and are excellent candidates for a hybrid rule-plus-model approach — a regex-based extractor for the common, regular cases with the NER model catching irregular phrasings, since paying full model-training cost for a pattern regex already solves well is wasted effort; `AMENITY` is open-ended and benefits most from active learning, since the set of amenities mentioned in real listings grows over time and a fixed initial training set will miss new ones without a continuous labeling loop.

| Symptom | Cause | Fix |
|---|---|---|
| Reported F1 is suspiciously high (98%+) on a task that seems hard | Evaluation is scoring at the token level, not the entity level, and the corpus is dominated by `O` tags | Recompute with `seqeval` or equivalent entity-level exact-match scoring before trusting the number |
| Model performs well in eval but extracted entities are subtly wrong in production (off-by-one-token boundaries) | Subword-to-word label alignment bug — labels applied to the wrong subword token, or inconsistent between training and inference | Verify alignment with `tokenizer.word_ids()` (or equivalent) on both the training and inference path; add a unit test with a multi-subword entity |
| Model outputs illegal tag sequences (e.g. `I-LOC` directly after `O`) | No CRF layer, or CRF transition matrix not properly constraining illegal transitions | Add or fix the CRF layer's transition constraints (mask illegal transitions to `-inf` rather than merely learning them as low-probability) |
| New entity type added to the schema performs far worse than existing types | Too few labeled examples for the new type relative to what the others had at launch | Prioritize the new type in the active learning queue; don't evaluate it against the same confidence thresholds as mature, well-represented types |
| Annotation budget exhausted before reaching target F1 | Random sampling for annotation instead of active learning | Switch to uncertainty (or hybrid uncertainty+diversity) sampling; published results show ~66% fewer annotated sentences needed for the same F1 versus random sampling |
| Nested or overlapping entities (a city name inside a full airport name) are silently mangled | Standard BIO/BIOES tagging assumes flat, non-overlapping spans | Redesign the schema to avoid the nesting where possible, or adopt a nested-NER-specific architecture/layered extraction pass if the nesting is unavoidable |

---

## Tradeoffs & when NOT to use it

- **Don't train a full BiLSTM-CRF or fine-tuned transformer NER model for a handful of highly regular entity types (prices, dates, flight numbers).** Regex and rule-based extraction is faster to build, faster to run, and perfectly precise on genuinely regular patterns; reserve the trained model for entity types with real linguistic variability the rules can't capture.
- **Don't skip the CRF layer if downstream logic depends on structurally valid output.** A transformer-only token classifier rarely produces illegal sequences, but "rarely" isn't "never," and a booking pipeline that occasionally receives a malformed date span is a worse failure than the modest added complexity of a constrained CRF decoding layer.
- **Don't evaluate with token-level metrics and report the number as NER performance.** This is the single most common way an NER project's reported accuracy misleads stakeholders; always use entity-level exact-match F1 (`seqeval` or equivalent) as the number that ships to a dashboard.
- **Don't manually annotate a random sample when annotation budget is the binding constraint.** Active learning's uncertainty sampling is a large, well-established, low-risk win (roughly 66% fewer annotations for the same target F1 in published clinical-domain results) whenever labeling is expensive relative to available budget.
- **Don't reach for an LLM-based zero-shot extraction pipeline as the default at high document volume.** It's the right choice for a new, rapidly-changing, or low-volume entity schema where standing up a fine-tuned model isn't worth the engineering cost; it's the wrong choice at the throughput (thousands of documents/second) most content platforms actually need, where a fine-tuned transformer or BiLSTM-CRF model's cost-per-document is a fraction of an LLM call's.

---

## Interview questions

### Q1 — Why does a linear-chain CRF fix the label bias problem that MEMMs have?
**Answer:** MEMMs normalize transition probabilities locally, per step, which structurally biases the model toward states with fewer outgoing transitions regardless of what the actual observation supports. A CRF normalizes globally via the partition function `Z(x)`, which sums over the score of every possible full tag sequence at once — no state is penalized just for having a smaller local branching factor, because normalization happens once, over the whole sequence, not step by step.
**Follow-up trap:** *"Does this mean CRFs are always better than MEMMs?"* — better on this specific structural issue, not universally; CRFs are more expensive to train (global normalization needs the full forward-backward pass) and the label bias problem is only a meaningful practical issue when the transition structure is genuinely skewed — naming the specific mechanism, not just picking the "modern" answer, is what's being tested.

### Q2 — Derive why computing the CRF partition function naively is exponential, and how forward-backward fixes it.
**Answer:** Naively, `Z(x) = Σ_y' exp(score(x, y'))` sums over every possible tag sequence — `T^n` of them for `T` tags and `n` tokens, exponential in sequence length. The forward algorithm exploits that the score decomposes into a sum of local terms depending only on adjacent tag pairs, so partial sums can be computed with dynamic programming: the forward variable at position `t` for tag `j` aggregates all paths ending at `j` at position `t`, computed from position `t-1`'s forward variables in `O(T)` work per position, giving `O(n*T^2)` total instead of `O(T^n)`.
**Follow-up trap:** *"Is this the same computation used for training and for prediction?"* — no; forward-backward (both directions) computes the quantities needed for the training gradient (expected feature counts), while Viterbi (a similar but distinct DP, using max instead of sum) computes the single best sequence for prediction/decoding — conflating the two is a common mistake.

### Q3 — Walk through BiLSTM-CRF's architecture and explain what each half is responsible for.
**Answer:** The BiLSTM (fed word embeddings concatenated with a character-level CNN or LSTM representation) is a learned feature extractor, producing a contextual vector per token — this replaces the hand-engineered features (word shape, gazetteers, suffixes) a classical CRF used. The CRF layer on top takes those learned per-token scores as emissions and performs the same globally-normalized structured scoring and Viterbi decoding as a classical CRF, learning transition weights between tags. The two halves are cleanly separable: swap the BiLSTM for any other contextual encoder (a transformer) and the CRF layer's job is unchanged.
**Follow-up trap:** *"Why include character-level features specifically?"* — they capture morphological and orthographic signal (capitalization, suffixes like "-ton" or "-ville" suggesting a place name, digit patterns) that generalizes to out-of-vocabulary and misspelled words, where a word-level embedding lookup alone has no signal at all — directly analogous to why fastText's subword approach helps with OOV words.

### Q4 — Does fine-tuned transformer NER need a CRF layer? Argue both sides.
**Answer:** Often not, in practice — a strong pretrained encoder's contextual representations already implicitly encode enough sequential structure that illegal tag transitions (an `I-PER` right after an unrelated `O`) become rare, and many production systems drop the CRF layer for a simple per-token softmax to reduce training complexity. But "rare" isn't "never," and any downstream system that cannot tolerate an occasional structurally invalid output (a booking pipeline parsing a malformed date-entity boundary) benefits from keeping a CRF layer, which provides an actual guarantee against illegal sequences via constrained Viterbi decoding, not just a statistical tendency away from them.
**Follow-up trap:** *"How would you measure whether the CRF layer is worth keeping for a specific deployment?"* — measure the rate of illegal-sequence errors on a held-out set with and without the CRF layer, and weigh that against the downstream cost of each such error — this is a measured tradeoff specific to the deployment, not a universal rule either way.

### Q5 — Explain BIO vs. BIOES tagging and when the added complexity of BIOES is worth it.
**Answer:** BIO tags each token as beginning, inside, or outside an entity (`2k+1` tags for `k` types); BIOES adds explicit end (`E-`) and single-token (`S-`) tags (`4k+1` tags), giving the model explicit signal about where an entity *ends*, not just where it starts. This measurably helps boundary detection on longer entities and disambiguating adjacent same-type entities, at the cost of a larger, more confusable label space. It's worth the added complexity when you've specifically measured a gain on your own data and your entities are frequently multi-token or adjacent; it's not worth adopting by default over BIO's simplicity and universal tooling support without that measurement.
**Follow-up trap:** *"Would you expect BIOES to help more or less for single-token entities like most PRICE mentions?"* — less; BIOES's main advantage is explicit end-boundary signal for multi-token spans, so for a schema dominated by single-token entities, BIO's simplicity wins with little accuracy to gain from switching.

### Q6 — Why is token-level F1 a misleading metric for NER, concretely?
**Testing:** the single most important evaluation trap in this module.
**Answer:** Real NER corpora are dominated by `O` (outside-entity) tokens — often 80-95%+ of all tokens — so a model predicting `O` for everything scores high token accuracy while extracting zero entities. Entity-level F1 (computed via `seqeval` or equivalent) requires an exact span-and-type match: same start token, same end token, same type, with no partial credit for a boundary that's off by one token. A predicted span cut short by even one token counts as both a false positive and a false negative under strict entity-level scoring.
**Follow-up trap:** *"If entity-level scoring is strict, doesn't that undercount models that are 'almost right'?"* — yes, deliberately: a downstream system consuming a malformed boundary (extracting "Seattle to" instead of "Seattle" as an origin city) fails just as badly as if the entity were missed, so the strict convention reflects real downstream cost rather than being unnecessarily harsh.

### Q7 — Design an active learning loop for a new travel-domain entity type your model currently performs poorly on.
**Answer:** Score the unlabeled pool with the current model and rank by uncertainty — margin between the top-1 and top-2 Viterbi-decoded sequence scores for a CRF-based model, or aggregated token-level entropy for a softmax-based transformer — send the highest-uncertainty sentences to annotators first, retrain, and repeat. Combine with diversity sampling (cluster sentence embeddings, ensure selected examples span different regions of the input distribution) to avoid uncertainty sampling repeatedly picking near-duplicate hard examples from one narrow slice of the data.
**Follow-up trap:** *"How do you know when to stop the active learning loop?"* — track entity-level F1 on a fixed held-out validation set after each round and stop when the marginal F1 gain per newly labeled batch drops below a threshold that makes further annotation not worth the cost — a diminishing-returns stopping rule, not a fixed round count decided in advance.

### Q8 — A hotel-description NER model tags "Four Seasons" as a single `HOTEL_NAME` entity in some sentences and splits it into two separate mentions in others. Diagnose.
**Answer:** Likely a boundary/tokenization inconsistency — check first whether "Four Seasons" is being split across a subword tokenization boundary inconsistently between training and inference (word-to-subword label alignment bug), and second whether the training data itself has inconsistent gold annotations for multi-word brand names (some annotators tagging "Four" and "Seasons" as separate entities, others as one span) — annotation guideline ambiguity is a very common real cause of this exact symptom, not just a model failure.
**Follow-up trap:** *"How would you fix inconsistent annotation guidelines after the fact, without relabeling everything?"* — audit a sample of existing annotations for the specific ambiguous pattern, write an explicit annotation-guideline rule for multi-word brand/entity names, and prioritize relabeling only the flagged inconsistent examples via active learning rather than a full relabel — targeted correction, not wholesale redo.

### Q9 — Your NER model needs to extract nested entities — a city name inside a full airport name ("Seattle-Tacoma International Airport" containing "Seattle"). How do you handle this?
**Answer:** Standard BIO/BIOES tagging assumes flat, non-overlapping spans and cannot natively represent one entity nested inside another. Options: redesign the schema to avoid the nesting if the inner entity isn't actually needed as a separate extraction (tag the whole airport name as one span and derive the city separately via a lookup or rule), run a layered extraction pass (extract the outer span first, then re-run a focused extractor on the span's text for the inner entity), or adopt an architecture built for nested NER (span-based or hypergraph-based models designed specifically for overlapping spans) if nested extraction is a hard requirement.
**Follow-up trap:** *"Is a nested-NER architecture usually worth the added complexity?"* — usually not, for most production schemas; the layered-extraction or schema-redesign workaround is simpler to build, test, and debug, and nested-NER architectures are worth the real complexity cost only when nesting is frequent and both the inner and outer entities are independently needed downstream.

### Q10 — Compare fine-tuned transformer NER against zero-shot LLM entity extraction for a production content pipeline. When does each win?
**Testing:** the senior cost/throughput tradeoff for this whole module.
**Answer:** Fine-tuned transformer (or BiLSTM-CRF) NER wins at high document volume where per-document inference cost and latency matter — a fine-tuned model's cost per document is a small fraction of an LLM API call's, and throughput of thousands of documents/second is realistic for a fine-tuned model but not for LLM calls at reasonable cost. Zero-shot LLM extraction wins for a new, rapidly changing, or low-volume entity schema, where the engineering cost of collecting labeled data and fine-tuning a model isn't justified by the volume, or where the schema changes often enough that a fine-tuned model would need frequent retraining.
**Follow-up trap:** *"What about using the LLM to bootstrap training data for the fine-tuned model?"* — a genuinely common and effective hybrid: use LLM extraction to weakly label a large unlabeled corpus quickly, have humans review/correct a sample (active-learning-prioritized), and use that as training data for a cheaper fine-tuned model that then serves production traffic — this captures the LLM's flexibility for schema bootstrapping without paying LLM inference cost per production document.

### Q11 — What's the difference between the emission scores and transition scores in a CRF, and where does each come from in a BiLSTM-CRF?
**Answer:** Emission scores are per-token, per-tag scores — "how well does this token's features support tag `T`" — and in BiLSTM-CRF they come from a linear projection of the BiLSTM's contextual hidden state at that token. Transition scores are per-tag-pair — "how good is it to go from tag `A` to tag `B`" — and are a learned matrix independent of the specific input, shared across the whole sequence, capturing structural/grammatical regularities like "an `I-TYPE` tag should virtually never directly follow `O`."
**Follow-up trap:** *"Could the transition matrix be made input-dependent instead of a fixed learned matrix?"* — yes, and some architectures do this (transition scores conditioned on context), trading the CRF's clean global structure and efficient exact decoding for potentially richer modeling — worth naming as a real design space, not treating the fixed transition matrix as the only possible CRF formulation.

### Q12 — How would you evaluate whether a new custom entity type is ready to ship, given it has far fewer labeled examples than your mature entity types?
**Answer:** Report entity-level F1 for the new type separately, not blended into an overall micro/macro-averaged score that a mature, well-represented type could mask; report a confidence interval or at minimum the raw support count (number of gold instances) alongside the F1, since F1 from a handful of examples is a noisy estimate; and set the bar for "ready to ship" based on downstream error tolerance for that specific entity type, not a blanket threshold copied from the mature types.
**Follow-up trap:** *"The new type's F1 looks fine but the sample size is tiny. Do you ship it?"* — no, not on that evidence alone; flag it as high-uncertainty, prioritize it in the active learning queue to grow the evaluation set before trusting the number, and consider shipping behind a feature flag or with human review on that entity type specifically until the estimate is more reliable.

### Q13 — Why might a hybrid rule-plus-model approach beat a pure NER model for entities like `PRICE` or `FLIGHT_NUMBER`?
**Answer:** These entity types have highly regular surface forms (currency symbols and digit patterns for price, airline-code-plus-digits patterns for flight numbers) that a regex or rule-based extractor handles with near-perfect precision and zero training cost. Paying full model training and inference cost to solve a pattern a five-line regex already solves reliably is wasted engineering effort; reserve the trained model's capacity for entity types with genuine linguistic variability (hotel names, amenities, destinations) that rules can't capture.
**Follow-up trap:** *"What if the regex misses an edge case the model would have caught?"* — run both and reconcile: use the regex as a high-precision first pass and fall back to (or cross-validate against) the model for cases the regex doesn't match, rather than treating it as strictly either/or — this is the same retrieve-then-verify pattern that shows up across many production NLP pipelines.

### Q14 — What specifically goes wrong if subword-to-word label alignment is implemented incorrectly in a transformer NER fine-tuning pipeline?
**Answer:** If a multi-subword word's label is applied inconsistently — for instance, applying the full word's `B-TYPE` label to every one of its subword pieces rather than only the first, with the rest either masked from the loss or explicitly relabeled `I-TYPE` — the model receives a corrupted training signal that doesn't match how predictions are actually reassembled to word-level spans at inference time. This silently degrades boundary accuracy in a way that's easy to miss in aggregate metrics but shows up as inconsistent behavior on multi-subword entity names specifically (exactly the "Four Seasons" symptom from Q8).
**Follow-up trap:** *"How would you catch this bug before it ships?"* — a unit test with a known multi-subword entity (a made-up brand name guaranteed to tokenize into multiple subwords) asserting the full pipeline — tokenize, align labels, train one step, decode, reassemble to word-level spans — round-trips correctly; this is a cheap, high-value test that catches the single most common transformer NER implementation bug.

### Q15 — Design the end-to-end entity extraction pipeline for tagging structured fields across a large hotel-listing content corpus (destinations, amenities, room types, prices) that needs to scale to millions of documents.
**Testing:** synthesis across schema design, architecture choice, and evaluation.
**Answer:** Split the schema by regularity: `PRICE` and structured numeric/date fields go through a regex/rule-based extractor for near-perfect precision at negligible cost. `DESTINATION` and `ROOM_TYPE`, moderately regular with a bounded vocabulary, are strong candidates for a fine-tuned BiLSTM-CRF or lightweight transformer NER model, trained and evaluated with entity-level F1 via `seqeval`, kept fast and cheap enough to run on every document at corpus scale. `AMENITY`, open-ended and growing over time, benefits most from an active learning loop (uncertainty sampling to prioritize labeling effort) and periodic model refresh as new amenity phrasings appear in the corpus. Bootstrap all of the model-based types' initial training data via LLM-based weak labeling on a sample, human-reviewed, rather than fully manual annotation from scratch. State explicitly that a single architecture for the whole schema is the wrong call — this is a portfolio of extraction methods matched to each field's regularity and volume, not one model.
**Follow-up trap:** *"How do you handle a brand-new hotel chain with entity names the model has never seen?"* — this is the fastText/OOV analogy for NER: character-level features in a BiLSTM-CRF (or subword tokenization in a transformer) give partial generalization to novel names via morphological/orthographic similarity to known entities, but the honest answer names this as a real, ongoing gap that active learning and periodic retraining manage rather than solve once and for all.

---

## Red flags that fail you

- Reporting token-level accuracy or F1 as the headline NER metric without checking entity-level (span-exact-match) F1.
- Not knowing why a CRF's global normalization (via the partition function) fixes the label bias problem MEMMs have.
- Claiming BIOES is strictly better than BIO without acknowledging the tradeoff (larger, more confusable label space) or that the gain must be measured, not assumed.
- Not knowing that subword tokenization requires explicit word-to-subword label alignment, or treating it as a solved non-issue.
- Reaching for a full trained NER model for highly regular entity types (prices, IDs) a regex already solves.
- Proposing random sampling for annotation when active learning is a well-established, large, low-risk cost reduction.
- Not knowing standard BIO/BIOES tagging can't represent nested or overlapping entities natively.
- Treating LLM-based zero-shot extraction as strictly superior to fine-tuned NER without naming the throughput/cost crossover.

---

## Cheat card

```
CRF (linear-chain)   score(x,y) = Σ_i Σ_k λ_k f_k(y_{i-1}, y_i, x, i)
  P(y|x) = exp(score)/Z(x)   Z(x) = Σ_y' exp(score(x,y'))  ← GLOBAL norm, fixes MEMM label bias
  Z(x): naive O(T^n) → forward algorithm O(n*T^2) via DP
  training: gradient = expected feature counts (forward-backward) − observed counts
  decoding: VITERBI, O(n*T^2), finds single best legal sequence

BiLSTM-CRF (2015-16)   word emb + char-CNN/LSTM (OOV/morphology signal) → BiLSTM → CRF layer
  BiLSTM/char-CNN = learned features (replaces hand-built: shape, gazetteers, suffixes)
  CRF layer unchanged from classical formulation — just takes learned emissions
  CoNLL-2003 English: low-mid 90s F1, no hand-crafted gazetteers needed

TRANSFORMER NER   BERT + token-classification head. Often DROPS the CRF layer (strong encoder
  rarely emits illegal sequences). Keep CRF if downstream needs a hard structural guarantee.
  SUBWORD ALIGNMENT: label first subword only, mask/relabel rest — misalignment = silent bug.
  SOTA CoNLL-2003 ~93-94 F1.

TAGGING SCHEME   BIO: 2k+1 tags, default, universal tooling.
  BIOES/BILOU: 4k+1 tags, explicit End+Single — helps longer/adjacent entities, MEASURE the gain.

CUSTOM ENTITIES   granularity, overlap/nesting (BIO can't represent nested spans natively),
  class imbalance across types — all real design decisions, not free schema additions.

ACTIVE LEARNING   uncertainty sampling (margin of top-1/top-2 Viterbi score, or entropy) >>
  random sampling: ~66% fewer annotated sentences for same target F1 (clinical NER, published).
  diversity sampling complements it (avoids near-duplicate hard-example selection).

EVAL   ENTITY-LEVEL F1 (seqeval, exact span+type match, NO partial credit), NOT token-level.
  Corpus is 80-95%+ "O" tokens — token accuracy is near-meaningless as a headline number.

TRAVEL ENTITIES   ORIGIN/DESTINATION, TRAVEL_DATE, AIRLINE, FLIGHT_NUMBER, HOTEL_NAME, ROOM_TYPE,
  PRICE, DURATION, LOYALTY_ID, AMENITY. Regex for PRICE/dates/IDs, model for the linguistically
  variable ones (HOTEL_NAME, AMENITY), active learning for open-ended/growing types.
```

## Sources

- [Conditional Random Fields: Probabilistic Models for Segmenting and Labeling Sequence Data — Lafferty, McCallum, Pereira, 2001](https://repository.upenn.edu/cgi/viewcontent.cgi?article=1162&context=cis_papers) — accessed 2026-08-02
- [Bidirectional LSTM-CRF Models for Sequence Tagging — Huang, Xu, Yu, 2015](https://arxiv.org/abs/1508.01991) — accessed 2026-08-02
- [Neural Architectures for Named Entity Recognition — Lample et al., 2016](https://arxiv.org/abs/1603.01360) — accessed 2026-08-02
- [BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding — Devlin et al., 2018](https://arxiv.org/abs/1810.04805) — accessed 2026-08-02
- [seqeval: entity-level sequence labeling evaluation](https://github.com/chakki-works/seqeval) — accessed 2026-08-02
- [Named Entity Recognition: Entity Types, BIO Tagging & Evaluation — Michael Brenndoerfer](https://mbrenndoerfer.com/writing/named-entity-recognition-ner-tutorial) — accessed 2026-08-02
- [A Study of Active Learning Methods for Named Entity Recognition in Clinical Text — PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC4934373/) — accessed 2026-08-02
- [Utilizing active learning strategies in machine-assisted annotation for clinical NER — JAMIA, 2024](https://academic.oup.com/jamia/article-abstract/31/11/2632/7724491) — accessed 2026-08-02
- [Machine Learning Scientist III, NLP at Expedia Group — WORK180 (Bayesian, LDA, NER, Random Forests requirements)](https://work180.com/en-us/for-women/employer/expedia/job/458598/machine-learning-scientist-iii-nlp) — accessed 2026-08-02

## Changelog
- 2026-08-02 — created
