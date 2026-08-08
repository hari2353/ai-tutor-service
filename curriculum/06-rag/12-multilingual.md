# Multilingual Embeddings, Cross-Lingual Retrieval, 22-Locale Reality

> **Track:** T06 RAG (Retrieval-Augmented Generation) · **Time:** 2.0h · **Prereqs:** 02-embeddings-choice · **Updated:** 2026-08-01
> **Module id:** `T06-multilingual` · **Tags:** retrieval,critical

## The 30-second version

Multilingual embedding models are trained so that translated or semantically equivalent sentences across languages land near each other in one shared vector space, which is what makes cross-lingual retrieval possible at all — a Japanese query can retrieve an English document with no shared vocabulary because the training objective explicitly pulled their meanings together, not their tokens. The 22-locale reality breaks three assumptions English-only engineers make by default: tokenizers are not equally efficient across languages (fertility — tokens per word — is measurably worse for morphologically rich and non-Latin-script languages, which is a direct cost and latency tax, not just a quality nuance), a single aggregate retrieval metric hides a completely broken locale because 21 healthy languages can mathematically absorb one collapsed language's score, and script/segmentation issues (CJK word boundaries, RTL rendering, transliteration between scripts) each need their own handling rather than one universal pipeline. The operational decision that actually matters at 22-locale scale is per-language evaluation as a hard requirement, not an optional nice-to-have, plus a routing strategy (shared index with language-aware retrieval vs. per-language indexes) chosen based on how differently your languages actually perform, not assumed uniform.

## Why this gets asked

The interviewer has shipped a multilingual RAG system that scored well in English QA testing, then watched a single locale silently degrade in production for weeks because the team was only watching a blended, corpus-wide metric — and the fix required someone to go looking language-by-language before anyone noticed. They want to know if you treat "multilingual" as a checkbox (swap in a multilingual embedding model) or as an operational discipline requiring per-locale evaluation, routing decisions, and cost awareness that a single-language system never has to think about.

---

## Lineage: past → present → future

**What came before.** Early cross-lingual retrieval relied on machine translation as a preprocessing step — translate the query (or the entire corpus) into a single pivot language, typically English, and run monolingual retrieval from there. The pain: translation quality varies wildly by language pair and domain, translation errors compound directly into retrieval errors with no way to distinguish "translation was wrong" from "retrieval was wrong," and translating an entire corpus at ingest time doubles storage and adds a slow, expensive preprocessing stage that has to be rerun on every corpus update. A second early approach, cross-lingual word embeddings (aligning separately-trained monolingual word vector spaces via a learned linear mapping), was cheaper but weaker — it aligned words, not sentence-level or passage-level meaning, and broke down on idioms, word order differences, and anything beyond near-literal translation.

**Where it stands now.** Multilingual sentence/passage embedding models trained with a contrastive objective across parallel and comparable corpora — pairs of sentences known or inferred to be translations or paraphrases of each other, pulled together in vector space during training — are the dominant approach, because they map meaning directly into one shared space without a separate translation step, and generalize better to non-literal cross-lingual similarity than word-alignment methods ever did. BGE-M3 (multilingual, 100+ languages, native support for dense + sparse + multi-vector retrieval in one model) is the strongest widely-used open-weight option; Cohere's `embed-v4` (100+ languages, competitive top-tier MTEB multilingual scores) is the leading commercial API option, with the corpus data sovereignty question (self-host vs. API) usually deciding between them more than raw quality difference. The live disagreement in 2026 is not "does cross-lingual retrieval work" — it demonstrably does for major languages — but how much per-language quality variance is acceptable before you need per-language routing or per-language index strategies rather than one shared multilingual index, and how much the industry underinvests in genuinely low-resource languages relative to the handful that dominate benchmark leaderboards.

**Where it's heading.** Research into tokenizer fairness across languages (metrics like Single Token Retention Rate, alongside the older "fertility" measure) is active and pushing toward tokenizers explicitly designed to be more equitable across scripts and morphology rather than optimized primarily for English — real and shipping in newer tokenizer releases (e.g. IndicSuperTokenizer for Indic languages), moderate confidence this becomes standard practice across all major model releases rather than a niche optimization. A 2025 large-scale study across 70 languages found that fertility alone does not explain most of the variance in downstream model performance, which complicates the simple "lower fertility = better" heuristic and is push toward more nuanced diagnostics — this is an open, unsettled research question, not resolved guidance. More speculative: fully joint multilingual-multimodal retrieval models that handle transliteration, code-switching, and script variation as a single learned problem rather than requiring separate normalization pipelines per language family.

---

## Mental model

One shared vector space, but the *path* into that space differs by language, and the path length differs too:

```
   "cancel my subscription" (English)  ──┐
   "annuler mon abonnement" (French)   ──┼──►  shared embedding space
   "サブスクリプションを解約" (Japanese) ──┤        (trained to cluster
   "अपनी सदस्यता रद्द करें" (Hindi)      ──┘         translation-equivalent
                                                      meanings together)

   BUT the tokenizer path to get there is NOT equal:
   English:   "cancel my subscription"        → ~4 tokens
   Japanese:  "サブスクリプションを解約"        → ~8-12 tokens (worse fertility,
                                                   no whitespace word boundaries)
   Hindi:     "अपनी सदस्यता रद्द करें"          → ~10-15 tokens (morphologically
                                                   richer, less training data)

   Same meaning, same destination vector neighborhood — different cost,
   different latency, different quality ceiling to get there.
```

The retrieval success at the end (does the right document come back) and the cost/latency to get there (how many tokens did that query actually cost) are two separate axes, and a system that only measures the first will be blind to the second degrading silently as locale mix shifts.

---

## How it actually works

### How multilingual embedding spaces are trained, and why cross-lingual retrieval works

Multilingual embedding models are trained with a contrastive objective over pairs of text known (parallel corpora, machine-translated data, or mined comparable corpora) or inferred (via weak supervision, e.g. Wikipedia inter-language links) to express the same meaning across languages — the loss function pulls matched cross-lingual pairs together and pushes unmatched pairs apart, the same InfoNCE-style contrastive objective used for monolingual embedding training, just with training pairs spanning languages instead of staying within one. The result is a genuinely shared space: a query and a document that mean the same thing land near each other in cosine similarity regardless of which language either was written in, because the training signal never distinguished "close because same language" from "close because same meaning" — it only ever optimized for the latter.

This is why cross-lingual retrieval works at all without any translation step at query time: the embedding model has already learned the cross-lingual meaning correspondence during training, so encoding a Japanese query and an English document with the same model puts them in the same neighborhood if they're actually about the same thing.

### Model options and the coverage-vs-quality tradeoff

| Model | Languages | Notes |
|---|---|---|
| BGE-M3 (open weights) | 100+ | Strongest open-source multilingual option; natively supports dense, sparse (BM25-like), and multi-vector (ColBERT-like) retrieval from one model — useful for hybrid without three separate models. Self-hostable, relevant for data-sovereignty requirements. |
| Cohere `embed-v4` (API) | 100+ | Leading commercial multilingual option, competitive top-tier MTEB multilingual scores; 128K context. No self-hosting. |
| Multilingual E5 | 100 | Well-documented, widely benchmarked open-weight family; a common baseline in academic comparisons. |
| Language-specific fine-tunes | 1 (or a small family) | Outperform general multilingual models on their specific language(s), at the cost of needing N models instead of one for N languages — a real operational tradeoff at 22-locale scale (N model deployments vs. one, but each is stronger on its language). |

The general pattern: broader language coverage in one model tends to trade off against peak quality on any single language relative to a language-specific model, and against the very-low-resource tail specifically, where a "100+ languages" claim often means competent-to-weak performance on the bottom 20-30 languages by training data volume, not uniform quality across all 100+.

### The 22-locale reality

**Tokenizer fertility and its cost.** Fertility — tokens produced per word (or per character, for non-whitespace-segmented scripts) — varies substantially by language, and this is a direct, measurable cost, not just a quality nuance: non-English languages routinely pay 1.5-2x+ the per-character token cost of English on many tokenizers, meaning the same semantic content costs more to embed, more to fit inside a context window, and more to serve at the same latency budget, purely as a function of which language the user happens to be typing in. This compounds across a pipeline — more tokens per query means more compute for embedding, more chunks needed to cover the same semantic content in a fixed chunk-token-size budget, and (if an LLM is in the loop) more generation cost per equivalent answer.

**Script variation.** Latin-script languages (English, French, Spanish) tokenize relatively efficiently with whitespace-aware tokenizers; non-Latin scripts (Cyrillic, Arabic, Devanagari, CJK) frequently do not, both because tokenizer training data historically skewed toward Latin-script text and because some scripts have fundamentally different structure (no case, different diacritic handling, combining characters).

**Right-to-left languages** (Arabic, Hebrew) introduce a rendering and mixed-content problem distinct from retrieval itself: a document mixing RTL prose with LTR numbers, code, or embedded English terms needs correct bidirectional text handling in both storage/display and in any chunk boundary logic that assumes left-to-right reading order — a naive chunker that splits "by character position" can produce a chunk that reads correctly stored but renders visually scrambled.

**CJK segmentation.** Chinese, Japanese, and Korean text has no whitespace between words, so both classical lexical retrieval (BM25 needs term boundaries) and any word-level preprocessing require a dedicated segmenter (e.g. Jieba for Chinese, MeCab for Japanese) — running a whitespace-based tokenizer on CJK text either treats each character as its own token (destroying multi-character word meaning for lexical scoring) or fails to segment at all.

**Transliteration.** Users frequently type queries in Latin script for languages that are natively written in another script — romanized Hindi ("kaise kare" for "कैसे करें"), pinyin for Chinese — and a retrieval system that only indexes the native script silently fails these queries unless transliteration is handled explicitly, either by normalizing at index time, at query time, or training/choosing a model with transliteration robustness.

**Low-resource languages.** Languages with little training data (in both the embedding model's pretraining and any tokenizer's training corpus) get weaker embeddings, worse tokenizer fertility, and are the languages most likely to be silently underperforming inside a "100+ languages supported" model claim — this is exactly the tail where per-locale evaluation matters most and is most often skipped.

### Per-language vs. shared index, and the operational cost of each

**Shared index (one multilingual embedding model, one vector index, language stored as metadata):** Simpler to operate — one index to maintain, one model to serve, queries route to the same infrastructure regardless of language. Risk: a shared index means every query, regardless of language, competes against the same corpus, and if the embedding model's cross-lingual alignment is imperfect for a given language pair, cross-lingual "leakage" (a Japanese query returning marginally-relevant Vietnamese documents because both happen to embed closer to each other than to the correct Japanese document) can degrade precision in ways that are hard to see in a blended metric.

**Per-language index (separate index per locale, language detected/declared and routed accordingly):** Isolates each language's retrieval quality and lets you use a language-specific embedding model where the general multilingual model underperforms, at the operational cost of N indexes to build, monitor, keep warm, and reindex — multiplying every operational task (capacity planning, monitoring, incident response) by locale count. At 22 locales, this is a real cost, not a rounding error.

**Practical middle ground**: shared index with language-aware retrieval augmentation — language stored as a filterable metadata field (pre-filtered or boosted, see `14-metadata-design`), plus language-specific handling only where the shared multilingual model measurably underperforms (a targeted fine-tune or a lexical-leg improvement for a specific low-resource language) rather than defaulting to full per-language index sharding everywhere.

### Language detection and routing, and mixed-language queries

Language identification models (fastText's `lid.176`, trained on Wikipedia/Tatoeba/SETimes data covering 176 languages) are the standard lightweight approach — the compressed model is under 1MB and reports F1 scores in the high-0.9s on clean, single-language text, fast enough to run per-query with negligible latency overhead. The harder case is **mixed-language queries** — code-switching within a single query ("what's the estado del clima today"), which single-label language detection handles poorly by design, since it assumes one dominant language per input. The practical mitigation is requesting top-k language predictions (not just the top-1) and treating a low-confidence or closely-contested top-2 as a signal to either run retrieval in both candidate languages and fuse results, or fall back to the shared multilingual embedding space directly (which doesn't require knowing the language at all, since the model was trained to be language-agnostic at the meaning level) rather than forcing a single-language routing decision that's likely wrong.

### Evaluating retrieval per-locale, and the silent-degradation failure mode

**The failure mode, named precisely:** a corpus-wide, blended recall@k or nDCG metric can stay flat or even improve while one specific locale collapses, because that locale's queries are a small fraction of total eval volume and its degradation is mathematically absorbed by the other 21 healthy languages' scores. The observable symptom in production is a slow trickle of complaints or ticket volume from users of one specific language, with no corresponding movement in the dashboard the team is actually watching — by the time it's noticed through support tickets rather than monitoring, it may have been degraded for weeks.

**The fix is structural, not just "check more carefully":** every retrieval eval must report metrics **per locale**, not only blended, as a hard requirement at any meaningful locale count — a golden set stratified by language with per-language recall@k/nDCG reported and alerted on independently. A system with 22 locales needs 22 (or at least a representative, monitored subset of) per-locale metric lines, not one number.

---

## Build it from scratch

```python
# untested sketch — illustrates the mechanics of language-aware routing and
# per-locale evaluation reporting, not a production multilingual pipeline
from collections import defaultdict

def route_query(query: str, lang_detector, embed_shared, embed_lang_specific: dict, confidence_threshold: float = 0.6):
    """Route to a language-specific model only when confident and available;
    otherwise fall back to the shared multilingual model, which needs no
    language label to function."""
    predictions = lang_detector.predict(query, k=2)  # [(lang, confidence), ...]
    top_lang, top_conf = predictions[0]
    if top_conf >= confidence_threshold and top_lang in embed_lang_specific:
        return embed_lang_specific[top_lang](query), top_lang
    return embed_shared(query), "shared"  # ambiguous / low-resource / mixed-language


def per_locale_eval(golden_set: list[dict], retrieve_fn, k: int = 10) -> dict[str, float]:
    """golden_set: [{'query':..., 'lang':..., 'relevant_ids': set(...)}]
    Returns recall@k PER LANGUAGE, not blended -- this is the whole point."""
    hits_by_lang: dict[str, list[int]] = defaultdict(list)
    for item in golden_set:
        retrieved_ids = {r["id"] for r in retrieve_fn(item["query"], top_k=k)}
        hit = 1 if retrieved_ids & item["relevant_ids"] else 0
        hits_by_lang[item["lang"]].append(hit)
    return {lang: sum(hits) / len(hits) for lang, hits in hits_by_lang.items()}
    # a blended average of this dict's values is exactly the metric that hides
    # a single collapsed locale -- report the dict, not just its mean
```

---

## How it's done in production

**Embedding models**: BGE-M3 (self-hosted, dense+sparse+multi-vector in one model, strong for hybrid), Cohere `embed-v4` (API, 100+ languages), Multilingual E5 (open, widely benchmarked). **Language detection**: fastText `lid.176` (176 languages, sub-millisecond, compressed `.ftz` variant under 1MB for edge/low-latency deployment). **CJK segmentation**: Jieba (Chinese), MeCab/Sudachi (Japanese), dedicated tokenizers rather than whitespace splitting. **Per-locale monitoring**: golden sets stratified by language with independent recall@k/nDCG dashboards and alerting per locale, not a single blended number (`13-accuracy-tuning`).

| Symptom | Cause | Fix |
|---|---|---|
| One locale's support tickets rise steadily while the overall retrieval dashboard looks fine | Blended metric absorbing one collapsed locale's score among 21 healthy ones | Report and alert on recall@k/nDCG per locale, not only blended; treat any single-locale metric drop as its own incident |
| A specific language's embedding cost and latency are unexpectedly high relative to others | Poor tokenizer fertility for that language/script — more tokens per unit of meaning | Measure tokens-per-query by locale explicitly; budget cost/latency per locale rather than assuming uniform cost across languages |
| Romanized queries for a non-Latin-script language return nothing | No transliteration handling — index only has native-script content, query arrives in Latin script | Normalize via transliteration at index or query time, or select/fine-tune a model with demonstrated transliteration robustness |
| CJK lexical (BM25) retrieval performs far worse than expected | Whitespace-based tokenization applied to a script with no whitespace word boundaries | Use a dedicated segmenter (Jieba, MeCab) before lexical indexing, not the default tokenizer |
| Code-switched or mixed-language queries route to the wrong single-language pipeline | Language detector forced into a single top-1 label on inherently mixed-language input | Use top-k language predictions; on low-confidence or contested top-2, fall back to the shared multilingual embedding space rather than a forced single-language route |
| A "100+ languages supported" model quietly underperforms for several of your active locales | Aggregate benchmark claims mask uneven per-language training data volume; low-resource languages in the tail are weaker by construction | Validate per-locale performance against your own golden set before trusting a vendor's aggregate multilingual claim |

---

## Tradeoffs & when NOT to use it

- **Don't ship a "100+ languages" embedding model without your own per-locale eval.** Aggregate benchmark scores are dominated by high-resource languages; your specific low-resource locales may sit far below the headline number, and the only way to know is to test them directly.
- **Don't default to per-language index sharding at every locale count.** It multiplies every operational task by the number of locales; a shared index with language-aware routing and targeted per-language fixes only where measurably needed is the more defensible default until evidence says otherwise for a specific language.
- **Don't force single-label language detection on inherently mixed-language input.** Code-switched queries are common in multilingual products (bilingual users, transliterated terms) and a forced single-language route on such queries actively makes retrieval worse than falling back to the shared, language-agnostic embedding space.
- **Don't treat tokenizer fertility as purely a quality nuance.** It is a direct cost and latency tax that compounds across embedding, chunking, and any downstream generation step — budget and monitor it per locale, especially for morphologically rich or non-Latin-script languages.
- **Don't assume translation-based cross-lingual retrieval is obsolete everywhere.** For genuinely low-resource languages with poor native embedding coverage, a translate-then-retrieve fallback (translate the query into a high-resource pivot language, retrieve, translate results back) can still outperform a multilingual embedding model that never saw enough of that language to align it well — this is a real, occasionally-correct exception to the "just use a multilingual embedding model" default.

---

## Interview questions

### Q1 — Mechanically, why does cross-lingual retrieval work at all with no translation step?
**Testing:** whether the candidate understands the training objective, not just that it "works."
**Answer:** Multilingual embedding models are trained with a contrastive objective over cross-lingual sentence/passage pairs known or inferred to share meaning, which pulls translation-equivalent text together in vector space regardless of language. The model never distinguished "similar because same language" from "similar because same meaning" during training — it only optimized for the latter — so encoding a query and document in different languages with the same model still places them near each other if they're actually about the same thing.
**Follow-up trap:** *"Does this work equally well for any language pair?"* — no, alignment quality depends on how much parallel/comparable training data existed for that language pair; high-resource pairs (English-French) align far better than low-resource ones.

### Q2 — What is tokenizer fertility, and why does it matter operationally, not just linguistically?
**Answer:** Fertility is tokens produced per word (or per character for non-whitespace scripts). Non-English, especially morphologically rich or non-Latin-script, languages routinely need 1.5-2x+ as many tokens as English for equivalent content on many tokenizers. This is a direct cost and latency tax — more tokens per query means more embedding compute, more chunks needed to cover the same content, and higher generation cost downstream — not merely a quality footnote.
**Follow-up trap:** *"Does lower fertility always mean better model performance for that language?"* — no; a 2025 70-language study found fertility alone explains relatively little of the variance in downstream performance, so it's a real cost signal but not a complete quality proxy.

### Q3 — Why is a single blended recall@k metric dangerous for a 22-locale product?
**Answer:** A blended metric averages across all locales, so one language's retrieval collapsing to near-zero can be mathematically absorbed by 21 other healthy languages, leaving the overall number flat or barely moved. The system looks fine on the dashboard while one locale is actually broken, and the failure typically surfaces through support tickets weeks later, not through monitoring.
**Follow-up trap:** *"How would you structurally prevent this?"* — report and alert on recall@k/nDCG per locale as a hard requirement, not an optional breakdown; a single blended number should never be the only thing on the dashboard.

### Q4 — Compare per-language indexes versus a shared multilingual index, with the real cost of each.
**Answer:** A shared index is operationally simpler (one index, one model, one monitoring surface) but risks cross-lingual leakage — imperfect embedding alignment letting a query surface marginally-relevant results from a different language — in ways a blended metric can hide. Per-language indexes isolate quality and allow language-specific models, at the cost of N indexes to build, monitor, keep warm, and reindex, multiplying every operational task by locale count.
**Follow-up trap:** *"Which would you default to?"* — shared index with language-aware routing/metadata filtering as the default, moving to per-language handling only for specific locales where evidence (per-locale eval) shows the shared model measurably underperforming — not a blanket architectural choice made up front.

### Q5 — How do you handle a query that mixes two languages in one input?
**Answer:** Single top-1 language detection forces an artificial single-language label on inherently mixed content and routes it wrong. Use top-k language predictions, and when the top-2 are close in confidence, either run retrieval across both candidate languages and fuse, or fall back to the shared multilingual embedding space directly, since it doesn't require a language label to function at all.
**Follow-up trap:** *"Why not just always use the shared multilingual model, then, and skip detection entirely?"* — because language-specific models or lexical legs (BM25 with proper segmentation) genuinely outperform the shared model for high-resource, unambiguous-language queries, so throwing away routing entirely loses real quality for the common case to protect the edge case.

### Q6 — What's specifically wrong with running a standard whitespace tokenizer on Japanese or Chinese text for lexical retrieval?
**Answer:** CJK scripts have no whitespace between words, so a whitespace-based tokenizer either treats every character as its own token (destroying multi-character word meaning that BM25's term statistics depend on) or fails to segment at all. A dedicated segmenter (Jieba for Chinese, MeCab for Japanese) is required before any lexical indexing or scoring.
**Follow-up trap:** *"Does this affect dense embedding retrieval the same way?"* — less directly, since modern subword tokenizers used by embedding models handle CJK at the subword level without requiring whitespace, but it still affects tokenizer fertility (more subword tokens per character for CJK on some tokenizers) and any preprocessing step that assumes word boundaries.

### Q7 — A user types a romanized query for a language natively written in a non-Latin script. What happens by default, and how do you fix it?
**Answer:** By default, nothing matches — the index holds native-script content and the romanized query shares no tokens or embedding-space proximity with it unless the embedding model happens to have learned transliteration robustness incidentally. The fix is explicit: normalize via transliteration at index time, at query time, or select/fine-tune a model demonstrated to handle transliteration for that language pair.
**Follow-up trap:** *"Isn't this a rare edge case?"* — no, romanized input is common and often the *default* input method for many non-Latin-script languages on mobile keyboards; treating it as rare is a real product-quality miss, not a hypothetical.

### Q8 — Why might low-resource languages underperform even inside a model advertised as supporting "100+ languages"?
**Answer:** Aggregate language-count claims say nothing about training data volume per language; low-resource languages by definition had less data to learn a well-aligned embedding space from, so they sit in the weaker tail of the same model's coverage. This is exactly why per-locale evaluation against your own golden set matters more than trusting the vendor's headline claim.
**Follow-up trap:** *"How would you improve a specific underperforming low-resource language without retraining the whole model?"* — options include a targeted fine-tune on available data for that language, a translate-to-pivot-language fallback specifically for that locale, or supplementing with a stronger lexical leg if the language has reasonable tokenization support even without strong embeddings.

### Q9 — When would translate-then-retrieve actually be the right call in 2026, despite multilingual embeddings being the modern default?
**Answer:** For a genuinely low-resource language where the multilingual embedding model's alignment is weak due to insufficient training data, translating the query into a high-resource pivot language, retrieving there, and translating results back can outperform a poorly-aligned multilingual embedding — the translation model may simply have more effective training signal for that language pair than the embedding model does.
**Follow-up trap:** *"Isn't that reintroducing the exact pain that motivated moving away from translation-based retrieval?"* — yes, and that's the honest tradeoff: it reintroduces translation-error compounding, but for a language where the alternative (a poorly-aligned embedding space) is worse, not better — the choice should be evidence-driven per language, not doctrinaire in either direction.

### Q10 — Design the per-locale evaluation and monitoring strategy for a 22-locale RAG product going into production.
**Testing:** synthesis and operational maturity.
**Answer:** Build a golden set stratified by language (ideally native-speaker-annotated per locale, not machine-translated from an English golden set, since translation artifacts distort what a real query looks like in that language). Report recall@k/nDCG per locale as a first-class metric, not a blended average, with independent alerting thresholds per locale so one language's degradation can't hide behind 21 healthy ones. Track tokenizer fertility and cost per locale separately, since cost/latency budgets are not uniform across languages. Route language detection with a confidence threshold and a shared-embedding fallback for ambiguous/mixed-language queries. Re-run the full per-locale eval on every embedding model swap or reindex, since cross-lingual alignment quality can shift non-uniformly across languages even when the aggregate benchmark score improves.
**Follow-up trap:** *"What if you don't have native-speaker annotators for all 22 locales?"* — prioritize annotation effort by traffic volume and known risk (low-resource languages, non-Latin scripts), and be explicit with stakeholders about which locales are running on weaker, machine-assisted eval coverage rather than silently treating all 22 as equally validated.

---

## Red flags that fail you

- Assuming a multilingual embedding model with no translation step "just works" uniformly across all supported languages.
- Not knowing what tokenizer fertility is or that it has a direct cost/latency implication.
- Trusting a single blended retrieval metric as sufficient evidence a multilingual system is healthy.
- Applying a whitespace tokenizer to CJK text without mentioning segmentation.
- Forcing single-label language detection on inherently mixed-language/code-switched queries.
- Defaulting to full per-language index sharding without weighing its operational cost.
- Ignoring transliteration as a real, common input pattern rather than an edge case.

---

## Cheat card

```
WHY CROSS-LINGUAL WORKS   contrastive training on cross-lingual pairs pulls
    translation-equivalent MEANING together in one shared vector space -- no
    translation step needed at query time.

MODELS   BGE-M3 (open, 100+ langs, dense+sparse+multi-vector in one model)
         Cohere embed-v4 (API, 100+ langs, 128K ctx, top-tier multilingual MTEB)
         Multilingual E5 (open, widely benchmarked)
         -- "100+ languages" claims mask uneven per-language training data; low-
            resource tail is weaker. Verify per-locale, don't trust the headline.

FERTILITY   tokens/word varies by language & script. Non-English often 1.5-2x+
            English's per-char token cost -- direct cost/latency tax, compounds
            through embedding + chunking + generation. Fertility alone does NOT
            fully explain downstream quality (2025, 70-language study).

22-LOCALE REALITY   script variation (Latin vs Cyrillic/Arabic/Devanagari/CJK)
    · RTL (Arabic/Hebrew) needs bidi-aware chunking/rendering
    · CJK has no whitespace word boundaries -- needs dedicated segmenter
      (Jieba/MeCab), not default tokenizer
    · transliteration (romanized Hindi/pinyin) needs explicit handling or
      queries silently return nothing
    · low-resource languages = weakest embeddings + worst fertility + least
      training data, and most likely to be silently broken

SHARED vs PER-LANGUAGE INDEX   shared = simple, risks cross-lingual leakage in
    a way a blended metric hides. Per-language = isolated quality, N-times the
    ops cost (build/monitor/reindex per locale). Default: shared + routing,
    per-language only where evidence shows it's needed.

LANG DETECTION   fastText lid.176: 176 langs, <1MB compressed (.ftz), high-0.9s
    F1 on clean text. Mixed/code-switched queries: use top-k predictions, not
    top-1; low-confidence/contested top-2 -> fall back to shared embedding space.

THE SILENT-DEGRADATION FAILURE   one locale collapses, 21 healthy locales
    absorb it in a blended metric, dashboard stays flat, surfaces via support
    tickets weeks later. FIX: report + alert recall@k/nDCG PER LOCALE, always.

WHEN TRANSLATE-THEN-RETRIEVE STILL WINS   genuinely low-resource language where
    the multilingual embedding's alignment is weak -- translation model may have
    more effective signal for that language pair than the embedding does.
```

## Sources

- [Best Embedding Models for RAG in 2026: A Comparison Guide — StackAI](https://www.stackai.com/insights/best-embedding-models-for-rag-in-2026-a-comparison-guide) — accessed 2026-08-01
- [Multilingual E5 Text Embeddings: A Technical Report (arXiv:2402.05672)](https://arxiv.org/pdf/2402.05672) — accessed 2026-08-01
- [The Multilingual Token Tax: What Building AI for Non-English Users Actually Costs](https://tianpan.co/blog/2026-04-20-multilingual-token-tax-llm-production) — accessed 2026-08-01
- [Beyond Fertility: Analyzing STRR as a Metric for Multilingual Tokenization Evaluation (arXiv:2510.09947)](https://arxiv.org/html/2510.09947v1) — accessed 2026-08-01
- [The Tokenizer Tax: Quantifying and Explaining the Cross-Lingual Cost of Subword Tokenization for Indian Languages (arXiv:2607.24276)](https://arxiv.org/html/2607.24276) — accessed 2026-08-01
- [IndicSuperTokenizer: An Optimized Tokenizer for Indic Multilingual LLMs](https://openreview.net/forum?id=CSrGFB070m) — accessed 2026-08-01
- [Language identification — fastText](https://fasttext.cc/docs/en/language-identification.html) — accessed 2026-08-01
- [fasttext-langdetect — GitHub](https://github.com/zafercavdar/fasttext-langdetect) — accessed 2026-08-01

## Changelog
- 2026-08-01 — created
