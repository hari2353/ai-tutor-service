# Encoder Models: BERT, Bi-Encoders vs Cross-Encoders, When an Encoder Beats an LLM

> **Track:** T05 LLM Internals · **Time:** 2.0h · **Prereqs:** none · **Updated:** 2026-08-01
> **Module id:** `T05-bert-encoders` · **Tags:** internals,critical

## The 30-second version

BERT is a stack of Transformer encoder blocks trained with bidirectional self-attention, so every token attends to every other token in both directions at once — a decoder can't do this because it must mask future tokens to stay autoregressive. That bidirectionality makes encoders bad at generation but very good at *understanding* a fixed piece of text, which is why they still win at classification, NER, retrieval embeddings, and moderation: one forward pass, no decoding loop, no sampling. The architectural fork that actually matters in interviews is bi-encoder versus cross-encoder: a bi-encoder embeds query and document separately so document vectors are precomputable and search is a single ANN lookup, while a cross-encoder concatenates query and document and lets attention run jointly across both, which is far more accurate but requires one full forward pass per candidate and cannot be precomputed at all. Production systems use both — bi-encoder for O(1)-per-query search over millions of documents, cross-encoder for O(n) reranking over the shortlist a bi-encoder already narrowed down. If you can precompute a candidate's representation independent of the query, use a bi-encoder; if you need the model to look at query and document together, you're paying cross-encoder prices, so keep n small.

## Why this gets asked

The interviewer has watched someone try to run a cross-encoder over an entire corpus at query time and either time out or burn a GPU budget discovering why that doesn't scale, or watched the opposite mistake — a team defaulting straight to an LLM call for a task like intent classification or PII detection that a $0.0001-per-1000-tokens encoder handles in single-digit milliseconds. They want to know if you reach for the cheapest model that solves the problem, and whether you actually understand *why* a bi-encoder can be precomputed and a cross-encoder can't, rather than reciting "bi-encoder is faster, cross-encoder is more accurate" as an unexplained fact.

---

## Lineage: past → present → future

**What came before.** Pre-2018, sentence representations came from averaging static word embeddings (word2vec, GloVe) or from task-specific RNN/LSTM encoders trained from scratch per task. Both had the same structural pain: no shared, transferable representation of language. Every new classification task meant training an encoder from random initialization on whatever labeled data you had, which was usually small, so models underfit language itself and overfit the narrow task. ELMo (2018) took a first step by producing contextual embeddings from a bidirectional LSTM, showing that context-sensitive representations beat static ones, but LSTMs process sequentially and can't attend across arbitrary distances in one step. BERT (Devlin et al., 2018) killed both problems at once: pretrain one bidirectional Transformer encoder on massive unlabeled text with a self-supervised objective, then fine-tune a small task-specific head on top. The pain it eliminated was concrete — GLUE benchmark scores jumped by double digits on several tasks the day BERT was released, because for the first time the field had a genuinely transferable, bidirectional, attention-based sentence representation.

**Where it stands now.** BERT's core recipe (bidirectional encoder + masked-token pretraining + fine-tuning) is settled as the right shape for understanding tasks; what's changed is which pieces of the original recipe survived contact with ablation studies. RoBERTa (Liu et al., 2019) removed BERT's Next Sentence Prediction (NSP) objective entirely, trained on 10x more data with 8x larger batches for longer, and matched or beat BERT on every downstream task — the finding that stuck is that **NSP was not pulling its weight**; it was too easy a task (distinguishing a real next sentence from a sentence sampled from a different document) to teach useful discourse-level structure, and masked language modeling (MLM) alone did the real work. On pooling: the field converged that **mean pooling over token embeddings beats `[CLS]`-token pooling** for sentence embeddings on models not explicitly fine-tuned for it, because `[CLS]` in vanilla BERT was only ever trained via NSP, a discarded, weak objective, so its embedding was never optimized to summarize the sentence. Sentence-BERT (Reimers & Gurevych, 2019) formalized mean pooling plus a siamese/triplet fine-tuning objective specifically to produce useful sentence embeddings, and it's the basis of the `sentence-transformers` library, whose `SentenceTransformer` wrapper defaults to a mean-pooling module over any base transformer today [Sentence Transformers — Modules](https://sbert.net/docs/package_reference/sentence_transformer/modules.html) — accessed 2026-08-01. The live disagreement is architecture modernization: ModernBERT (Warner et al., Dec 2024) rebuilt the encoder with rotary position embeddings, Flash Attention, alternating local/global attention, and an 8192-token context window trained on 2T tokens of text and code, showing that the plain 2018 BERT architecture had been leaving real accuracy and throughput on the table for years simply by not adopting decoder-side advances (RoPE, GeGLU) that had already proven out. Encoder-specific embedding variants (`nomic-ai/modernbert-embed-base`, `lightonai/modernbert-embed-large`) now ship with prompt-aware query/document formatting baked into training [ModernBERT embeddings — Hugging Face](https://huggingface.co/nomic-ai/modernbert-embed-base) — accessed 2026-08-01.

**Where it's heading.** High confidence: encoders are not being displaced by decoder-only LLMs for their core jobs — classification, NER, retrieval, moderation — because the cost and latency gap is structural, not a matter of model quality catching up. A 2026 cost-model study found fine-tuned encoders deliver equal-or-better accuracy than LLM prompting for fixed-label classification at one to two orders of magnitude lower inference cost [Cost-Aware Model Selection for Text Classification](https://arxiv.org/html/2602.06370v1) — accessed 2026-08-01, and industry estimates put encoders at roughly 15-250x faster and 20-200x more energy-efficient than LLMs at equivalent classification accuracy [Alternatives to LLMs in 2026](https://www.metacto.com/blogs/beyond-the-hype-exploring-powerful-alternatives-to-llms-for-your-next-ai-project) — accessed 2026-08-01. Moderate confidence: encoder-only architectures keep absorbing decoder-side efficiency tricks (ModernBERT's RoPE and Flash Attention, LFM2.5-Encoders' CPU-optimized long-context design) rather than being replaced by them. Speculative: whether a unified encoder-decoder or a single frontier model eventually subsumes the need for separately trained encoders for narrow tasks — there's no evidence this is close, and every current signal points the other way, toward smaller, cheaper, more specialized encoders as the default first choice for high-volume understanding tasks, with generative LLMs reserved for tasks that actually require generation.

---

## Mental model

```
ENCODER-ONLY (BERT)              DECODER-ONLY (GPT)            ENCODER-DECODER (T5)
  bidirectional attention          causal (masked) attention     encoder: bidirectional
  every token sees every token     token i sees tokens <= i      decoder: causal + cross-attn
  good at: understanding           good at: generation           good at: seq2seq (translate,
  bad at: generating text          bad at: needs full context        summarize)
  one forward pass -> a vector     needs a decoding loop         two passes: encode once,
  or per-token label set           to produce more than 1 token  decode with cross-attention

BI-ENCODER vs CROSS-ENCODER

  BI-ENCODER (independent)                CROSS-ENCODER (joint)
  query ─►[Encoder]─► q_vec                query+doc ─►[Encoder]─► score
  doc   ─►[Encoder]─► d_vec  (offline,             (one forward pass PER candidate,
                        once, precomputed)           query and doc attend to each other)
  score = cosine(q_vec, d_vec)             cannot be precomputed — score depends
                                            on the query, which you don't have offline

  precompute 10M doc vectors once -> ANN lookup is O(log N) or O(1)-ish per query
  cross-encoder over 10M docs = 10M forward passes per query -> never do this
  cross-encoder over a 100-doc shortlist = 100 forward passes -> fine, ~50-150ms
```

The one thing to internalize: a bi-encoder's accuracy ceiling is set by compressing an entire document into one fixed-size vector *before* it has ever seen the query — it can never ask "does this specific document actually answer this specific question," only "is this document generally similar to this query." A cross-encoder removes that ceiling by letting attention run across both texts jointly, at the cost of never being able to compute anything offline.

---

## How it actually works

### The architecture: what "encoder-only" actually means

A Transformer block is self-attention + feed-forward, repeated N times. The only structural difference between BERT and GPT is the attention mask:

```python
# untested sketch — illustrates the mask difference, not a full implementation
def causal_mask(seq_len):
    # decoder (GPT): token i can only attend to tokens 0..i
    return torch.triu(torch.full((seq_len, seq_len), float("-inf")), diagonal=1)

def bidirectional_mask(seq_len):
    # encoder (BERT): every token attends to every token, no masking
    return torch.zeros((seq_len, seq_len))
```

That's the entire architectural delta. BERT-base is 12 layers, 768 hidden, 12 heads, 110M params; BERT-large is 24 layers, 1024 hidden, 16 heads, 340M params. Because there's no causal mask, BERT cannot be used to generate text left-to-right in the way GPT can — every position already "sees" the future, so there's no well-defined next-token distribution conditioned only on the past. This is also why BERT is not autoregressively sampled: it's used in one shot, or with masked positions.

### Pretraining objectives: MLM and NSP, and which one didn't survive

**Masked Language Modeling (MLM).** Randomly select 15% of tokens; of those, 80% become `[MASK]`, 10% are replaced with a random token, 10% are left unchanged. The model predicts the original token at each masked position using bidirectional context — it can use words both before *and* after the masked position, which a causal LM structurally cannot. This is the objective that does the real work.

**Next Sentence Prediction (NSP).** Feed two segments as `[CLS] A [SEP] B [SEP]`; 50% of the time B genuinely follows A, 50% of the time B is a random segment from elsewhere in the corpus. Predict real/random from the `[CLS]` output. **RoBERTa's ablation showed this was close to useless** — the task was too easy (topic mismatch alone solves most random cases) and dropping it while training longer, on more data, with larger batches, improved downstream performance. If an interviewer asks "what did BERT get wrong," NSP is the correct, specific answer, not a vague "the training could have been better."

### Pooling: turning per-token output into one vector

BERT emits one 768-dim vector per input token. To get a single sentence embedding, you must pool:

| Strategy | How | When it's right |
|---|---|---|
| `[CLS]` pooling | Take the first token's final-layer vector | Only after fine-tuning specifically makes `[CLS]` meaningful for that task (e.g., a classification head trained on top of it) |
| Mean pooling | Average all token vectors (masking out padding) | Default for sentence embeddings on models not fine-tuned toward `[CLS]` — this is why `sentence-transformers` defaults to it |
| Max pooling | Element-wise max across token vectors | Rarely best; ablations consistently rank it below mean |

Why mean pooling usually wins: in vanilla BERT, `[CLS]`'s only training signal was NSP — a weak, now-discarded objective — so its raw embedding was never actually optimized to summarize sentence meaning. Averaging every token's contextual embedding aggregates signal from the whole sequence instead of relying on one token that was never trained for the job. Sentence-BERT's own ablations found mean pooling outperforms `[CLS]` pooling on STS-B and NLI tasks [Pooled Embeddings from SBERT](https://www.emergentmind.com/topics/pooled-embeddings-from-sbert) — accessed 2026-08-01. This flips once you fine-tune: a classifier trained with a head on `[CLS]` makes that token meaningful for that specific task, so `[CLS]` pooling is correct *after* task-specific fine-tuning, wrong as a default for general-purpose embeddings.

### Bi-encoder vs cross-encoder, stated precisely with the arithmetic

**Bi-encoder.** `f(query)` and `f(doc)` are computed independently, never seeing each other. Every document in the corpus is embedded once, offline, and stored in a vector index. At query time you embed the query (one forward pass) and do a nearest-neighbor lookup. Cost per query: **O(1) encoder forward pass + O(log N) or O(1)-amortized ANN lookup**, regardless of corpus size.

**Cross-encoder.** The model receives `[CLS] query [SEP] doc [SEP]` as one input and every token of the query attends to every token of the document (and vice versa) through every layer. The output is a single relevance score for that specific pair. Because the score is a function of both texts together, there is no way to precompute anything about the document in isolation — you must re-run the full forward pass for every (query, document) pair you want scored. Cost per query: **O(n) full forward passes**, where n is the number of candidates you score.

**The latency arithmetic, concretely.** An ANN search (HNSW) over 10M documents with a bi-encoder typically resolves in single-digit-to-low-double-digit milliseconds — you're doing one 768-dim encode plus a graph traversal, not touching most of the corpus. Reranking 100 candidates with a cross-encoder like BGE-reranker-v2-m3 costs roughly 50-100ms on GPU (batched) or on the order of 100-150ms on CPU per batch of candidates [see `T06-reranking` for the full economics table]. Run the cross-encoder over the *whole* 10M-document corpus instead of a 100-candidate shortlist and you're doing 10M forward passes per query — even at an optimistic 1ms/pair on a batched GPU that's 10,000 seconds, roughly three hours, per query. That gap (tens of milliseconds vs. hours) is the entire reason retrieve-then-rerank cascades exist: cheap bi-encoder or BM25 narrows 10M to 100-500, then the cross-encoder only ever has to do the expensive part on the small set.

**ColBERT as the middle ground.** Late interaction keeps a per-token embedding for both query and document (rather than pooling to one vector, and rather than running them jointly), and scores with MaxSim — for each query token, find its best-matching document token, sum those maxima. This recovers much of the cross-encoder's token-level precision while keeping document representations precomputable (they don't depend on the query), at the cost of storage that scales with total token count rather than document count. Full derivation and storage math live in `T06-hybrid-search`; don't re-derive it here, just know the positioning: bi-encoder (cheap, coarse) → ColBERT (precomputable, token-level precision, storage-heavy) → cross-encoder (most accurate, not precomputable, only viable on a shortlist).

### When an encoder beats a generative LLM — the senior signal

This is the question that actually separates candidates. For **classification, NER, retrieval embeddings, and moderation**, a fine-tuned encoder:

- Needs one forward pass, not a decoding loop — no output tokens to sample, so latency is a small, fixed cost independent of "how much" the model wants to say.
- Is 15-250x faster and 20-200x more energy/cost-efficient than an LLM prompted for the same fixed-label task, at equal or better accuracy on production-scale evaluations [Cost-Aware Model Selection for Text Classification](https://arxiv.org/html/2602.06370v1) — accessed 2026-08-01.
- Produces a deterministic, bounded output space (a probability distribution over K fixed labels, or a fixed-dimension vector) instead of free text you then have to parse and validate.
- Is small enough to run on CPU or a cheap GPU instance at high QPS, where an LLM call would need a GPU-backed inference endpoint and still cost 10-100x more per request.

The failure mode to name explicitly: teams that reach for an LLM prompt to do intent classification or PII/toxicity detection because "we already have the LLM in the stack," and end up paying generative-model latency and cost for a task with a small, fixed label set that a $0 marginal-cost encoder call would solve in under 10ms. The senior answer isn't "encoders are old, LLMs are new" — it's "match the model to the shape of the output": fixed labels and embeddings want an encoder, open-ended text generation wants a decoder.

---

## Build it from scratch

Minimal fine-tuning of an encoder for classification (no lab folder exists yet for this module — this is the from-scratch shape to internalize):

```python
# untested sketch
from transformers import AutoTokenizer, AutoModel
import torch, torch.nn as nn

tok = AutoTokenizer.from_pretrained("bert-base-uncased")
base = AutoModel.from_pretrained("bert-base-uncased")

class EncoderClassifier(nn.Module):
    def __init__(self, base, n_classes, pooling="mean"):
        super().__init__()
        self.base = base
        self.pooling = pooling
        self.head = nn.Linear(base.config.hidden_size, n_classes)

    def forward(self, input_ids, attention_mask):
        out = self.base(input_ids=input_ids, attention_mask=attention_mask).last_hidden_state
        if self.pooling == "cls":
            pooled = out[:, 0]                       # [CLS] token — only right AFTER fine-tuning
        else:
            mask = attention_mask.unsqueeze(-1).float()
            pooled = (out * mask).sum(1) / mask.sum(1).clamp(min=1e-9)   # mean pooling
        return self.head(pooled)

model = EncoderClassifier(base, n_classes=3, pooling="mean")
```

Building a minimal bi-encoder vs cross-encoder retrieval pair to feel the precomputation difference:

```python
# untested sketch
def biencoder_score(query_vec, doc_vecs):
    # doc_vecs precomputed once, offline; this is the only work at query time
    return doc_vecs @ query_vec / (doc_vecs.norm(dim=1) * query_vec.norm())

def crossencoder_score(cross_model, tok, query, doc):
    # must run the full model for THIS (query, doc) pair — no offline shortcut exists
    inputs = tok(query, doc, return_tensors="pt", truncation=True)
    return cross_model(**inputs).logits.item()
```

Run the bi-encoder path against 10,000 synthetic vectors and the cross-encoder path against 10,000 (query, doc) pairs and time both — the wall-clock gap you'll see is the entire argument for cascades.

---

## How it's done in production

| Framework/model gives you | What it adds |
|---|---|
| `sentence-transformers` (SBERT) | Siamese/triplet fine-tuning objectives purpose-built for embeddings, mean pooling by default, a huge model zoo, and a stable API for training and inference |
| ModernBERT | RoPE, Flash Attention, alternating local/global attention, 8192-token context, trained on 2T tokens of text+code — a modernized base architecture for both classification and embeddings |
| `nomic-ai/modernbert-embed-base` / `lightonai/modernbert-embed-large` | Prompt-aware query/document embedding formats baked into training, so query and document text are encoded asymmetrically on purpose |
| Managed reranker APIs (Cohere rerank-3.5, Voyage rerank-2) | Cross-encoder as a hosted call, no GPU ops burden — see `T06-reranking` for the cost/latency table |
| ColBERT / PLAID | Token-level late interaction with a production-grade serving engine — see `T06-hybrid-search` |

**Failure modes**

| Symptom | Cause | Fix |
|---|---|---|
| Reranker p99 latency blew the request budget | Cross-encoder run over hundreds of candidates synchronously in the request path | Shrink the shortlist (top 20-50, not top 500) or move reranking off the hot path |
| Embedding quality is worse than expected out of the box | Using raw BERT `[CLS]` pooling without SBERT-style fine-tuning | Switch to mean pooling, or use a model actually trained for sentence embeddings (SBERT, ModernBERT-embed) |
| Retrieval finds topically-similar but wrong-answer documents | Bi-encoder ceiling — a single vector can't capture query-document interaction | Add a reranking stage; a bi-encoder alone is a first-stage retriever, not a final-answer filter |
| Fine-tuned classifier degrades on a new label distribution | Classification head trained on `[CLS]` from a checkpoint whose `[CLS]` was never meaningfully pretrained (older BERT, no fine-tuning yet on this task) | Fine-tune end-to-end rather than freezing the base; verify pooling strategy matches how the checkpoint was actually trained |
| Encoder "can't do" a task the team assumes needs an LLM | Reaching for a decoder model out of habit for a fixed-label problem | Check whether the output space is actually free text (needs a decoder) or fixed/bounded (encoder is cheaper and often more accurate) |

---

## Tradeoffs & when NOT to use it

- **Don't use a bi-encoder as your final ranking signal for high-stakes top-k.** It's a first-stage retriever. If precision on the top 5-10 results matters (customer-facing search, legal/medical retrieval), you need a reranking stage.
- **Don't run a cross-encoder over more than a few hundred candidates in a synchronous request.** The forward-pass-per-candidate cost doesn't amortize; it's linear, and at real-time latency budgets that ceiling is low. If you find yourself wanting to cross-encode thousands of candidates, you have a first-stage recall problem to fix, not a reranker-scaling problem.
- **Don't use an encoder when the task genuinely requires generation** — summarization, open-ended Q&A, code writing. Encoders don't produce free text; forcing a fixed-label or extractive framing onto a generative task loses information the task actually needed.
- **Don't assume `[CLS]` pooling works out of the box on a base checkpoint you haven't fine-tuned.** It's the single most common reason "we tried BERT embeddings and they were bad" turns out to be a pooling-strategy bug, not a model-quality problem.
- **When an LLM is still the right call over an encoder**: the label space isn't fixed or known in advance (zero-shot open-set classification with no fine-tuning data), the task requires reasoning across the text rather than pattern-matching it, or you need natural-language justification alongside the label. An encoder gives you a label or a vector; it can't explain itself.

---

## Interview questions

### Q1 — Why can't a decoder-only model use bidirectional attention?
**Testing:** whether you understand the architectural reason, not just the label.
**Answer:** A decoder is trained to predict the next token given only the tokens before it. If it could attend to future tokens during training, it would trivially "cheat" by looking at the answer it's supposed to predict — the causal mask exists specifically to prevent that. An encoder has no such constraint because it isn't predicting the next token in a sequence; it's building a representation of a text it's already fully seen.
**Follow-up trap:** *"So could you just remove the mask from GPT and get BERT?"* — no. Removing the mask alone doesn't fix the training objective; you'd also need to change from causal LM to something like MLM, because training an unmasked model with a next-token objective leaks the answer at every position and the loss becomes meaningless.

### Q2 — What did RoBERTa change, and why does it matter?
**Answer:** Dropped Next Sentence Prediction, trained on roughly 10x more data with much larger batches for longer, and matched or beat BERT on every downstream task. It matters because it isolated which piece of BERT's recipe was actually doing the work — MLM — and which was dead weight — NSP, which was too easy a discrimination task to teach useful structure.
**Follow-up trap:** *"Does that mean NSP-style objectives are always useless?"* — no, the lesson is narrower: *that specific* NSP formulation (real vs. random-from-corpus sentence) was too easy. Objectives that force genuinely hard discourse-level discrimination (e.g., sentence order prediction, used later in ALBERT) survived better, so the takeaway is "ablate your auxiliary objectives," not "auxiliary objectives never help."

### Q3 — When would you use `[CLS]` pooling vs mean pooling?
**Answer:** Mean pooling by default for sentence embeddings, especially on a checkpoint not specifically fine-tuned for embeddings — `[CLS]` in vanilla BERT was only ever trained via the weak NSP objective, so its raw vector isn't optimized to summarize meaning. `[CLS]` pooling is correct once you've fine-tuned a classification head directly on top of it, because that fine-tuning is what makes the token meaningful for that specific task.
**Follow-up trap:** *"`sentence-transformers` — what does it default to?"* — a mean-pooling module is created automatically when you wrap a plain transformer checkpoint that isn't already a `SentenceTransformer` model; know this cold, it's the kind of detail that separates "read about it" from "used it."

### Q4 — Precisely: what's the difference between a bi-encoder and a cross-encoder?
**Answer:** A bi-encoder encodes query and document independently — neither ever sees the other during encoding — so document vectors are precomputable and stored once; at query time you do one encode plus an ANN lookup, cost independent of corpus size. A cross-encoder concatenates query and document into one input and lets attention run jointly across both through every layer, producing a score that depends on both texts together, so it cannot be precomputed and must be re-run for every candidate you want scored.
**Follow-up trap:** *"Why can't you just cache the cross-encoder's document-side computation?"* — because the joint attention means the document's internal representations at every layer are influenced by the query tokens attending into them; there's no clean separation point where you could freeze a "document-only" intermediate state and reuse it across different queries.

### Q5 — Give me actual numbers: reranking 100 candidates vs. an ANN search over 10M documents.
**Answer:** A bi-encoder ANN search (HNSW) over 10M docs resolves in single-digit-to-low-double-digit milliseconds — you never touch most of the corpus. Reranking the top 100 candidates with a cross-encoder like BGE-reranker-v2-m3 costs roughly 50-100ms on GPU. Running that same cross-encoder over the full 10M corpus instead of a 100-candidate shortlist would mean 10M forward passes — even at an optimistic 1ms/pair batched, that's on the order of hours per query, which is why nobody does it.
**Follow-up trap:** *"What if the first-stage retriever has bad recall?"* — reranking a weak shortlist perfectly still gives you the best of a bad set. The cascade's ceiling is set by first-stage recall, not by the reranker's accuracy; a common real bug is treating a reranking accuracy drop as a reranker problem when it's actually a first-stage retrieval problem.

### Q6 — Why does BERT need fine-tuning at all if it's already pretrained on huge amounts of text?
**Answer:** MLM pretraining teaches general bidirectional language structure, not any specific downstream task's label space or decision boundary. Fine-tuning adds a small task-specific head (a linear layer, typically) and adjusts the base model's weights (or just the head, for lighter fine-tuning) so the pretrained representations get mapped onto the actual labels or scores you need — this is `T05-finetuning`'s territory (frozen vs. partial vs. full fine-tune) applied specifically to an encoder base.
**Follow-up trap:** *"Could you skip fine-tuning entirely and use raw embeddings?"* — for retrieval-style tasks with a model already trained for embeddings (SBERT, ModernBERT-embed), yes, frozen embeddings work well out of the box. For classification with a novel label set, no — the base model has never seen your labels, so you need at minimum a trained head on top.

### Q7 — Your reranker is the bottleneck instead of retrieval. What do you do?
**Answer:** Shrink the shortlist — rerank the top 20-50 rather than the top 200-500 — since cross-encoder cost is linear in candidate count and this is almost always the highest-leverage fix. If that's not enough, move reranking off the synchronous request path (precompute for common queries, or accept a slightly higher latency budget with async scoring), or consider ColBERT-style late interaction if you need token-level precision at a lower per-query cost than a full cross-encoder.
**Follow-up trap:** *"Won't a smaller shortlist hurt recall?"* — only if the first-stage retriever's top-N at the smaller N is actually missing relevant documents; measure that specifically (recall@N for a few candidate N values) before assuming a smaller shortlist costs accuracy. Often the first 20-30 already contain everything relevant and the rest were adding latency with no benefit.

### Q8 — Design a moderation pipeline: encoder, LLM, or both?
**Testing:** whether you reach for the cheapest model that fits the output shape.
**Answer:** Encoder-first. Toxicity/PII/spam/policy-violation detection is fixed-label classification, and a fine-tuned encoder gets equal-or-better accuracy at one to two orders of magnitude lower cost and latency than prompting an LLM for the same labels. Reserve an LLM call for the genuinely ambiguous cases the encoder flags as low-confidence or borderline, where you actually need reasoning or nuance an encoder's fixed decision boundary can't capture.
**Follow-up trap:** *"What if policy categories change frequently?"* — that's the actual argument for an LLM in the loop: a fixed-label encoder needs retraining data for new categories, while a well-prompted LLM can be redirected instantly. The honest answer names this explicitly as the real tradeoff (retraining latency vs. per-request cost) rather than picking one model type as universally correct.

### Q9 — What's ColBERT, and how does it relate to bi-encoders and cross-encoders?
**Answer:** ColBERT keeps a per-token embedding for query and document instead of pooling to one vector, and scores via MaxSim — for each query token, find its best-matching document token and sum those maxima. Document token embeddings are precomputed independently of the query (like a bi-encoder), so it stays cheap at retrieval scale, but scoring recovers token-level interaction that a single pooled vector loses (closer to what a cross-encoder gives you), at the cost of storage that scales with total corpus token count rather than document count.
**Follow-up trap:** *"So is it just a cheap cross-encoder?"* — no, and saying so is the trap. It never jointly encodes query and document together; only the final MaxSim scoring step brings them together, using embeddings that were each computed in isolation. That's why it's precomputable and a true cross-encoder isn't — see `T06-hybrid-search` for the storage math.

### Q10 — What's the actual architectural difference between BERT and T5?
**Answer:** T5 is encoder-decoder: a bidirectional encoder processes the input once, then a causal decoder generates output tokens autoregressively while cross-attending into the encoder's output. BERT is encoder-only — it has no decoder and no mechanism to generate a sequence of new tokens. T5 is built for sequence-to-sequence tasks (translation, summarization) where the output is a different, possibly variable-length text; BERT is built for tasks where the answer is a label, a span within the input, or a fixed-size vector.
**Follow-up trap:** *"Could you use T5's encoder alone as a BERT replacement?"* — largely yes for embedding/classification purposes, since it's also a bidirectional Transformer encoder; some embedding models are in fact built on T5 encoders. The distinguishing question is whether you need the decoder at all, and if you don't, you're paying for parameters and complexity a plain encoder-only model doesn't need.

### Q11 — ModernBERT claims to modernize BERT. What did it actually change, and does it change your answer to "encoder or LLM"?
**Answer:** RoPE instead of learned absolute position embeddings, Flash Attention, alternating local/global attention layers, GeGLU activations, and an 8192-token context trained on 2T tokens of text and code — architectural and training upgrades borrowed from decoder-side progress, not a change to the fundamental bidirectional-encoder-plus-MLM recipe. It doesn't change the encoder-vs-LLM decision in kind, but it raises the ceiling on what encoders can do (longer documents, better throughput), which strengthens the case for encoders on tasks that used to be borderline due to context-length limits.
**Follow-up trap:** *"Is ModernBERT a drop-in replacement for BERT-base?"* — architecturally not literally drop-in (different position encoding, different tokenizer in most releases), but functionally yes as an upgrade path — same training/fine-tuning shape, better numbers, longer context. Framing it as "same job, better engine" is the correct level of precision.

### Q12 — A colleague wants to use GPT-4-class model to extract 5 fixed entity types from support tickets at 2M tickets/day. What do you tell them?
**Testing:** the senior signal — matching model to task shape under real cost pressure.
**Answer:** Push back and propose a fine-tuned NER encoder instead. Five fixed entity types is a bounded-output classification problem, and at 2M/day the cost and latency delta between an encoder and an LLM call compounds into a real infrastructure decision, not a rounding error — encoders run 15-250x faster and cheaper at comparable or better accuracy for exactly this shape of task. Reserve the LLM for entity types that are open-ended or context-dependent enough that a fixed schema can't capture them.
**Follow-up trap:** *"What if we don't have labeled training data for the 5 entity types?"* — that's the real constraint, and it's solvable without an LLM in the hot path: bootstrap labels with a one-time LLM pass over a sample, or few-shot the LLM to auto-label a training set, then train the encoder offline and run the cheap model at 2M/day scale. The LLM's right role here is as a labeling tool, not a per-request inference engine.

---

## Red flags that fail you

- Saying "cross-encoders are just slower bi-encoders" — they're not the same computation at a different speed, they're structurally non-precomputable.
- Not knowing why `[CLS]` pooling on a non-fine-tuned checkpoint underperforms mean pooling.
- Proposing a cross-encoder as a first-stage retriever over a full corpus.
- Reaching for an LLM prompt for a fixed-label classification task without considering an encoder.
- Describing RoBERTa's change vaguely ("trained better") instead of naming NSP removal specifically.
- Confusing ColBERT with a cross-encoder ("it jointly encodes query and doc") when it precomputes both sides independently.
- Not being able to state that BERT can't generate text because of the bidirectional attention, only classify or embed.

---

## Cheat card

```
ENCODER vs DECODER vs ENC-DEC
  encoder: bidirectional attn, understanding tasks, no generation
  decoder: causal attn, generation, autoregressive
  enc-dec (T5): bidirectional encode once + causal decode w/ cross-attn -> seq2seq

BERT PRETRAINING
  MLM: mask 15% (80% [MASK]/10% random/10% unchanged), predict original — DOES THE WORK
  NSP: real/random next-sentence — RoBERTa dropped it, matched/beat BERT anyway

POOLING
  [CLS]: only meaningful AFTER task-specific fine-tuning (its only pretrain signal was NSP)
  mean: default for general sentence embeddings; sentence-transformers defaults to this

BI-ENCODER vs CROSS-ENCODER
  bi:    f(q), f(d) independent -> precompute d offline -> O(1)/query ANN lookup
  cross: f(q,d) joint attention -> NOT precomputable -> O(n) fwd passes, n=candidates
  10M-doc ANN search: single-digit-low-double-digit ms
  cross-encoder on 100 candidates: ~50-100ms (GPU, batched)
  cross-encoder on full 10M corpus: ~hours/query — never do this
  ColBERT: per-token embeddings, precomputable, MaxSim scoring — middle ground

DISTILBERT / TINYBERT NUMBERS (compression, not this module's focus — see T05-transfer-distillation)
  DistilBERT: 97% of BERT perf, 40% smaller, 60% faster

WHEN ENCODER BEATS LLM
  fixed label space / embeddings -> encoder: 15-250x faster, 20-200x cheaper, equal/better acc
  open-ended generation / reasoning / justification needed -> LLM

WHEN NOT TO USE
  cross-encoder as sole ranker over full corpus -> too slow
  [CLS] pooling on non-fine-tuned checkpoint -> broken embeddings
  encoder for free-text generation -> wrong output shape
```

## Sources
- [Sentence Transformers — Modules (mean pooling default)](https://sbert.net/docs/package_reference/sentence_transformer/modules.html) — accessed 2026-08-01
- [Pooled Embeddings from SBERT — pooling ablations](https://www.emergentmind.com/topics/pooled-embeddings-from-sbert) — accessed 2026-08-01
- [nomic-ai/modernbert-embed-base — Hugging Face](https://huggingface.co/nomic-ai/modernbert-embed-base) — accessed 2026-08-01
- [ModernBERT: The Return of the Encoder](https://atalupadhyay.wordpress.com/2026/03/11/modernbert-the-return-of-the-encoder/) — accessed 2026-08-01
- [Cost-Aware Model Selection for Text Classification: Fine-Tuned Encoders vs LLM Prompting](https://arxiv.org/html/2602.06370v1) — accessed 2026-08-01
- [Alternatives to LLMs in 2026 — encoder cost/latency figures](https://www.metacto.com/blogs/beyond-the-hype-exploring-powerful-alternatives-to-llms-for-your-next-ai-project) — accessed 2026-08-01

## Changelog
- 2026-08-01 — created
