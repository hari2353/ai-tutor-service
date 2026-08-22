# Attribution & Grounding: Citations That Hold Up, Faithfulness vs Plausibility

> **Track:** T07 Agentic AI · **Time:** 2.5h · **Prereqs:** `T07-explainability`, `T06-hybrid-search`, `T06-chunking` · **Updated:** 2026-07-26
> **Module id:** `T07-attribution` · **Tags:** trust, critical

## The 30-second version

A citation that **exists** and a citation that **supports the claim** are different products, and the industry ships the first while claiming the second. The 2026 deep-research-agent audit makes the gap unmissable: 12 of 14 models scored above 94% on "the link works" and every frontier model above 80% on "the page is topically relevant", while **fact-check accuracy ranged from 24% to 77%** — so a user clicking a citation almost always lands on a real, on-topic page whose specific claim is unsupported roughly a third to half of the time. The structural cause is **post-hoc citation**: generate the answer from parametric memory, then search for sources that look like they agree, and attach them. That pipeline is a confirmation-bias machine, because retrieval returns topical similarity and the model was instructed to produce a citation, so it produces one. The fix is **grounded generation** — retrieve first, bind each sentence to a specific span, constrain the model to only cite ids that are actually in context — plus a **programmatic entailment gate** using an NLI checker on (cited chunk ⊨ sentence), and abstention when nothing entails. Measure it with ALCE-style citation recall and precision, report the unsupported-sentence rate as a headline number, and never let "the link resolves" appear in a dashboard as if it meant anything.

## Why this gets asked

Because the interviewer has personally watched a customer click one citation. That is the whole story. The demo goes beautifully for six weeks, then a subject-matter expert opens the linked policy section, does not find the sentence the assistant attributed to it, and the trust cost is not one answer — it is every answer that came before. The Stanford RegLab study of commercial legal research tools (Magesh, Surani et al., *Journal of Empirical Legal Studies* 2025) is the canonical public version: RAG-based products from LexisNexis and Thomson Reuters hallucinated in **17% to 33%** of responses against a GPT-4 baseline of 43%, while one vendor was marketing "100% hallucination-free linked legal citations". The interviewer wants to know whether you understand that **RAG reduces hallucination and does not eliminate it**, and whether you can name the mechanism that turns a grounded pipeline into a confidently mis-cited one. At staff level the probe becomes architectural: where in the pipeline does the citation get created, and is it a *constraint* on generation or a *decoration* added afterwards? Candidates who cannot answer that have never debugged a mis-citation.

---

## Lineage: past → present → future

**What came before.** The 2022 generation of chat products cited nothing, and the failure was total unverifiability: a fluent paragraph with no way to check any of it. The first response was prompt-level — "cite your sources" — and it produced the worst possible artefact: fabricated URLs, invented DOIs, plausible arXiv ids that resolve to unrelated papers, and case citations that do not exist. That specific failure has real-world consequences, with courts sanctioning filings containing fabricated citations. The research community then did the definitional work. **Rashkin et al. (2021, *Measuring Attribution in Natural Language Generation*)** gave the **AIS** criterion — *Attributable to Identified Sources*: a statement is attributable to source *s* if a generic reader would agree that "According to *s*, X" is true. **Bohnet et al. (2022)** built Attributed QA around it. **Gao et al. (ALCE, EMNLP 2023)** made it measurable at scale with NLI-based **citation recall** and **citation precision**, and **AttrScore** (Yue et al. 2023) gave the three-way label set *attributable / extrapolatory / contradictory* that is still the right vocabulary. Meanwhile **Liu, Zhang & Liang (Findings of EMNLP 2023, arXiv:2304.09848)** audited the shipping generative search engines and found, on average, only **51.5% of generated sentences fully supported by their citations and only 74.5% of citations supporting their associated sentence** — the numbers that killed "we added citations" as a sufficient answer.

**Where it stands now.** Four things are consensus. (1) **Sentence-level is the working granularity**, with claim-level (atomic-fact decomposition, FActScore-style) as the gold standard when you can afford it and response-level rejected as meaningless. (2) **NLI entailment is the standard automatic check**, and small specialised checkers beat prompting a frontier model on both cost and often accuracy — MiniCheck-FT5 (~770M, flan-t5-large) matches Claude 3 Opus and approaches GPT-4 on LLM-AggreFact at a small fraction of the cost, AlignScore-large is 355M on RoBERTa-large, and Vectara's HHEM-2.1-open is smaller still while outperforming several larger models. (3) **Grounded generation beats post-hoc attachment**, and "Attribute First, then Generate" (arXiv:2403.17104) is the canonical framing: select the evidence spans, then generate only from them. (4) **Surface metrics mislead** — the PwC deep-research audit (*Cited but Not Verified*, arXiv:2605.06635) showed link validity and topical relevance are near-saturated while fact-check accuracy spans 24-77%, and it found the counterintuitive result that **more search makes attribution worse**: GPT-5.4's fact-check accuracy fell from 79% at 2 tool calls to 17% at 150, with link validity and relevance staying above 92% the whole way. Their hypothesis is attention dilution during synthesis, and the corollary is that selective citation beats exhaustive citation.

The live disagreements. First, **whether automatic attribution metrics transfer**. 2026 audit work (*Do LLM Attribution Metrics Transfer?*, arXiv:2606.23915) finds metric agreement with human judgment varies substantially across datasets and constructs, which means an in-house citation-precision number is a *relative* instrument for tracking your own regressions and not a comparable absolute. Second, **entailment versus sufficiency of evidence**: *Relevant Is Not Warranted* (arXiv:2605.28044) argues a passage can technically entail a sentence while providing weak evidential force, so binary entailment over-credits weakly-supported claims — the proposed direction is calibrated evidence strength rather than a boolean. Third, **where attribution should be computed**: post-hoc verification (cheap, bolt-on, catches errors after the fact), citation-constrained decoding over a grammar (arXiv:2606.07130), or model internals (MIRAGE, arXiv:2406.13663, uses attention/gradient internals to attribute answer spans to context spans, which is cheap but requires white-box access and inherits the faithfulness objections from `T07-explainability`).

**Where it's heading.** High confidence: **verification becomes a pipeline stage, not a feature** — a small entailment model in the response path is already cheap enough that shipping unverified citations will read as negligence within a year or two, in the same way shipping without input validation does now. High confidence: **locator granularity tightens** from document to span, because a citation you cannot check in one click is a decoration; expect deep-link-with-highlight to become table stakes. Medium confidence: **citation grammars via constrained decoding** become the default implementation, since making it structurally impossible to emit an id that is not in context removes an entire class of bug at near-zero cost. Medium confidence: **evidence-strength scores replace boolean entailment** in high-stakes domains. Speculative, flag it as such: end-to-end trained attribution where the model's citation head is optimised directly against verified attribution, and provenance standards for generated text analogous to C2PA for images. Nothing to design around yet.

---

## Mental model

The ladder of citation strength. Every rung looks identical in the UI, and only the top two are worth anything.

```
  CITATION STRENGTH LADDER                          what a dashboard usually measures
  ─────────────────────────────────────────────────────────────────────────────────
  5  ENTAILED + LOCATED    the cited span entails the sentence,           ← the goal
                           and the locator points at that span
  4  ENTAILED              some part of the cited doc entails it          ✅ NLI gate
  ─────────────────────── everything below here is a DECORATION ──────────────────
  3  TOPICALLY RELEVANT    doc is about the right subject          80-96% of models
  2  RESOLVES              the URL/doc id exists and loads         94-100% of models
  1  WELL-FORMED           it looks like a citation                 ~100%
  0  FABRICATED            invented DOI / arXiv id / case number

  PwC 2026 deep-research audit: rung 2 ≈ 94-100%, rung 3 ≈ 80-96%,
  rung 4 (fact check) = 24-77%.  The gap between rung 3 and rung 4 IS the problem.
```

And the two pipelines. The difference is not a detail, it is the whole module.

```
POST-HOC CITATION  (what most systems do — a confirmation-bias machine)

  question ──▶ LLM generates answer FROM WEIGHTS ──▶ answer text
                                                       │
                            ┌──────────────────────────┘
                            ▼
              search for docs that LOOK LIKE they agree
                            │      (retrieval optimises SIMILARITY,
                            ▼       and similarity ≠ entailment)
              attach top-1 to each sentence ──▶ ✅ resolves ✅ relevant ❌ supports
                            │
                     the model was TOLD to cite, so it cites.
                     There is no step at which "no source supports this"
                     can be the output.  That is the bug.


GROUNDED GENERATION  (retrieve → constrain → verify → abstain)

  question ──▶ retrieve k chunks ──▶ SELECT evidence spans (extractive)
                                            │
                                            ▼
              generate ONLY from selected spans, emitting [id] tokens
              constrained to ids present in context
                                            │
                                            ▼
              per-sentence NLI gate:  cited_span ⊨ sentence ?
                          ├── yes ─────────▶ render as supported
                          ├── contradicts ─▶ DROP + log (retrieval conflict)
                          └── neutral ─────▶ mark unsupported, or ABSTAIN
                                            │
              "no sentence entailed" is a REACHABLE OUTPUT.  That is the fix.
```

One line to remember: **post-hoc citation asks "what supports what I already said?", grounded generation asks "what can I say given this evidence?"** The first question has an answer for every claim, true or false. The second one does not, which is exactly why it is safer.

---

## How it actually works

### Definitions, precisely

**AIS (Rashkin et al. 2021):** sentence *x* is attributable to source *s* if a generic, competent reader would agree that *"According to s, x"* is true, with *x* interpreted in the context of the full response. Two clauses do heavy lifting. "According to *s*" means truth in the world is not the test — a citation to a source that says something false is still *attributable*; the sentence's truth is a separate axis. And "interpreted in context" is why you must **decontextualise** a sentence before checking it, since "It was raised to 4.5% in March" is not checkable in isolation.

**ALCE metrics (Gao et al. 2023)** — memorise these, they get asked directly:

```
For sentence s with cited docs C = {d₁..dₘ}:

  citation RECALL(s)    = 1 if  concat(C) ⊨ s   else 0
                          "is the sentence supported by its citations at all?"

  citation PRECISION(s) = for each dᵢ ∈ C:  dᵢ counts as precise if
                            (a) dᵢ alone ⊨ s,  OR
                            (b) removing dᵢ breaks entailment: concat(C \ dᵢ) ⊭ s
                          "is every citation pulling its weight, or is it padding?"

  Report: mean recall over sentences, mean precision over citations,
          plus UNSUPPORTED-SENTENCE RATE = 1 − mean recall     ← headline number
```

Precision exists because of a specific gaming behaviour: cite five documents per sentence and recall goes up while the user's ability to check anything goes down. Precision penalises the shotgun.

**Faithfulness vs plausibility, for citations.** A citation is *plausible* when it resolves, sits on the right domain, and is topically on-point. It is *faithful* when the cited span entails the claim. The entire industry's dashboards measure plausibility, users experience plausibility right up until one of them checks, and only faithfulness survives the check. That framing is worth saying out loud in an interview because it connects to the same axis from `T07-explainability`.

### The four ways a citation fails

| Level | Failure | Frequency in 2026 frontier systems | Detection |
|---|---|---|---|
| 0 | **Fabricated** — invented DOI, arXiv id, case number | Rare with retrieval, still common closed-book | Resolve the id. Trivial and mandatory |
| 1 | **Wrong locator** — right document, wrong section/page | Common with document-level citations | Span-level locators; verify quote appears verbatim |
| 2 | **Relevant but unsupporting** — real, on-topic, does not contain the claim | **The dominant mode.** 24-77% fact-check accuracy | NLI entailment. Nothing cheaper works |
| 3 | **Supports but misleading** — cherry-picked, stale version, contradicted elsewhere in the corpus | Underreported because nobody tests it | Contradiction sweep across retrieved set; version/recency metadata |

Level 3 is the one that separates staff answers. A sentence can pass every entailment check and still be wrong because the assistant cited policy v1.4 when v2.1 supersedes it, or quoted the exception rather than the rule. The mitigation is not more entailment; it is corpus hygiene (retire superseded documents from the index, or carry `effective_from`/`superseded_by` metadata and filter at retrieval) plus a contradiction sweep: if two retrieved chunks disagree, surface the conflict instead of silently picking one.

### Why post-hoc citation produces confident wrong citations

Five mechanisms, and being able to list them is the answer to the module's core question:

1. **The answer already exists.** It was generated from parametric memory, so the retrieval step is not evidence-gathering, it is *evidence-seeking for a fixed conclusion*. That is the definition of confirmation bias, implemented in software.
2. **Retrieval optimises similarity, not entailment.** A dense retriever scores semantic relatedness. The chunk that is *most similar* to a claim is often the chunk that discusses the same topic and states the opposite, because negation barely moves an embedding. This is the single most important sentence in the module.
3. **The instruction guarantees output.** "Cite your sources" makes citation mandatory, and there is no reachable output that means "nothing here supports this". Compare a grounded pipeline, where abstention is a live branch.
4. **The verifier is the generator.** If the model both writes the claim and judges the support, its errors are perfectly correlated. Asking the same model "does this source support this?" recovers far less than an independent checker.
5. **Fluency hides the seam.** The citation marker is a token like any other; nothing in the decoder distinguishes `[3]` where doc 3 supports the claim from `[3]` where it does not.

The empirical signature, from the 2026 deep-research audit: link validity and topical relevance stay above 92% while fact-check accuracy collapses, and **it gets worse with more search** — 79% → 17% for GPT-5.4 between 2 and 150 tool calls. More sources means more opportunities to conflate. That is a genuinely counterintuitive finding and it is excellent interview material.

### Grounded generation: four techniques, increasing strength

**1. Retrieve-then-cite with ids in context (weak but standard).** Put chunks in context with explicit ids, instruct the model to cite only those ids. Cheap; fails because the instruction is soft. The model will still attribute a parametric fact to a present-but-unsupporting id.

**2. Citation-constrained decoding (strong, cheap, underused).** Make it *structurally impossible* to emit an id not in context, by constraining the token grammar at citation positions to the id set actually provided (arXiv:2606.07130). This kills fabricated ids outright at near-zero cost. It does not fix relevant-but-unsupporting, so it is necessary, not sufficient.

**3. Attribute-first / quote-then-write (strongest for faithfulness).** Two passes. Pass one is *extractive*: select the specific spans that answer the question, and nothing else. Pass two is *abstractive over the selected spans only*, with the original chunks removed from context. Because the generator can only see the selected quotes, every sentence is bound to a span by construction and attribution is local (arXiv:2403.17104). Costs: two calls, roughly 1.4-1.8x tokens, measurably lower fluency, and coverage drops because pass one can legitimately select nothing. That last property is a feature.

**4. Structured output with evidence binding.** Force a schema where every claim object carries its evidence id and quote:

```json
{"claims":[
  {"text":"Refunds are available within 30 days of the invoice date.",
   "evidence":[{"doc":"policy/refunds-v2.1","locator":"§3.2","quote":"Refunds are available within 30 days of the invoice date."}]},
  {"text":"INV-8841 was issued 2026-07-11.",
   "evidence":[{"doc":"billing/INV-8841","locator":"chars 400-460","quote":"Issued 2026-07-11"}]}
]}
```

Then **verify the quote appears verbatim in the cited document** — an exact string check, cost ~0, which catches paraphrased-quote fabrication that NLI will happily pass. Combine with constrained decoding for the id field and you have eliminated levels 0 and 1 mechanically before any model-based verification runs. Prose is assembled from verified claims at render time.

The hard ceiling on all of this: **you cannot cite what you did not retrieve.** Grounded generation converts a hallucination problem into a retrieval-recall problem. If the answer is in a document ranked 40th, grounded generation abstains and post-hoc citation confabulates; abstention is better, but the fix is retrieval (`T06-hybrid-search`, `T06-chunking`), not attribution.

### Granularity: response, sentence, claim

| Granularity | Verification calls per response | Use when |
|---|---|---|
| Response-level | 1 | Never. "Some of this is supported" is not a claim |
| **Sentence-level** | ~8-25 for a typical answer | **Default.** Matches how users check |
| Claim-level (atomic) | 3-8x sentence-level after decomposition | High-stakes: medical, legal, financial. FActScore-style |

Sentence-level has a specific bug you must handle: **decontextualisation**. "It was raised to 4.5% in March" has an unresolved pronoun and no subject, so an NLI model sees a hypothesis it cannot evaluate and returns neutral, producing a false "unsupported" flag. Resolve references against the preceding response text before checking. A cheap heuristic (prepend the answer's subject noun phrase when the sentence starts with a pronoun or has no proper noun) catches most cases; a small LLM rewrite is more robust and costs one call per response, not per sentence.

### Programmatic verification with NLI

Choose the checker on cost and premise length, not brand:

| Checker | Size | Notes |
|---|---|---|
| DeBERTa-v3-large-MNLI | ~400M | General NLI baseline. Trained on **short** premises; degrades on long chunks |
| AlignScore-large | 355M (RoBERTa-large) | Purpose-built factual-consistency alignment function |
| **MiniCheck-FT5** | ~770M (flan-t5-large) | Matches Claude 3 Opus / approaches GPT-4 on LLM-AggreFact at a fraction of the cost. Strong default |
| HHEM-2.1-open (Vectara) | smallest of the group | Outperforms several larger models; drives the Vectara leaderboard |
| LettuceDetect | small, token-level | Flags the *spans* that are unsupported, not just a verdict — better UX |
| Frontier LLM as judge | — | Most accurate on hard cases, 10-100x the cost, and correlated with your generator if same family |

Two engineering gotchas that are the real content here:

- **Premise length.** NLI models were trained on premise/hypothesis pairs of a couple of sentences. Feed a 1,500-token chunk as the premise and entailment probability drifts toward neutral. Fix: split the premise into sentences (or overlapping 3-sentence windows), score each against the hypothesis, and **max-pool** the entailment score. This also gives you the span-level locator for free, which is what you want in the UI anyway.
- **Thresholds are per-model and per-domain.** There is no universal 0.5. Calibrate on ~200 hand-labelled (claim, chunk, supported?) pairs from your own corpus, pick the threshold at your target precision, and re-calibrate when you change the checker or the chunker. And remember automatic attribution metrics do not transfer across datasets (arXiv:2606.23915), so your number tracks *your* regressions and is not comparable to a paper's.

Third-order concern worth naming: entailment is boolean and evidential force is not. *Relevant Is Not Warranted* (arXiv:2605.28044) shows passages that formally entail a claim while providing weak support. In high-stakes domains, prefer a graded evidence score plus a rule that a claim needs either strong single-source support or two independent sources.

---

## Build it from scratch

A citation verifier: decontextualisation, verbatim-quote check, sentence-split premises with max-pooling, ALCE recall/precision, and abstention. Written so the NLI call is injectable, so it runs with a stub.

```python
"""Citation verifier. python 3.11+, stdlib only (bring your own NLI callable).
Real use: nli = MiniCheck / AlignScore / HHEM-2.1-open, batched on GPU.
    python verify.py
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Callable, Iterable
import re

Nli = Callable[[list[tuple[str, str]]], list[float]]   # [(premise, hypothesis)] -> P(entail)

SENT = re.compile(r'(?<=[.!?])\s+(?=[A-Z0-9"\(])')
CITE = re.compile(r"\[([A-Za-z0-9_\-/\.:§]+)\]")


@dataclass
class Doc:
    id: str
    text: str

    def sentences(self) -> list[str]:
        return [s.strip() for s in SENT.split(self.text) if s.strip()]


@dataclass
class Verdict:
    sentence: str
    cited: list[str]
    recall: int                  # ALCE: 1 if union of cited docs entails sentence
    per_doc: dict[str, float]    # doc id -> max-pooled entailment score
    precise: dict[str, bool]     # doc id -> is this citation pulling its weight
    best_locator: dict[str, str] # doc id -> the premise sentence that carried it
    status: str                  # supported | unsupported | contradicted | uncited


def split_sentences(answer: str) -> list[str]:
    return [s.strip() for s in SENT.split(answer) if s.strip()]


def decontextualise(sentences: list[str]) -> list[str]:
    """Cheap heuristic: a sentence starting with a pronoun or lacking any capitalised
    token past position 0 inherits the subject of the first sentence. Prevents the
    classic false 'unsupported' on 'It was raised to 4.5% in March.'
    Replace with a one-call LLM rewrite per RESPONSE (not per sentence) for production."""
    if not sentences:
        return sentences
    subject_match = re.match(r"^([A-Z][\w\-]*(?:\s+[A-Z][\w\-]*)*)", sentences[0])
    subject = subject_match.group(1) if subject_match else None
    out = []
    for i, s in enumerate(sentences):
        needs = re.match(r"^(It|This|That|They|These|Those|He|She|Its|Their)\b", s)
        if i > 0 and needs and subject:
            s = f"{subject}: {s}"
        out.append(s)
    return out


def verbatim_quote_ok(quote: str, doc: Doc) -> bool:
    """Zero-cost check that catches paraphrased-quote fabrication, which NLI passes.
    Normalise whitespace and quote characters only; do NOT lowercase-fuzzy-match."""
    norm = lambda t: re.sub(r"\s+", " ", t.replace("’", "'").replace("“", '"')
                            .replace("”", '"')).strip()
    return norm(quote) in norm(doc.text)


def entail_maxpool(nli: Nli, doc: Doc, hypothesis: str,
                   window: int = 3) -> tuple[float, str]:
    """NLI models are trained on SHORT premises. Feeding a 1500-token chunk drives
    the score toward neutral. Split into overlapping windows, score each, max-pool.
    Side benefit: the winning window IS your span-level locator."""
    sents = doc.sentences() or [doc.text]
    windows = [" ".join(sents[i:i + window]) for i in range(max(1, len(sents) - window + 1))]
    scores = nli([(w, hypothesis) for w in windows])
    best = max(range(len(scores)), key=lambda i: scores[i])
    return scores[best], windows[best][:200]


def verify(answer: str, docs: dict[str, Doc], nli: Nli,
           tau: float = 0.60, contradict_tau: float = 0.70,
           nli_contradiction: Nli | None = None) -> list[Verdict]:
    raw = split_sentences(answer)
    hyps = decontextualise(raw)
    out: list[Verdict] = []

    for raw_s, hyp in zip(raw, hyps):
        cited = [c for c in CITE.findall(raw_s) if c in docs]
        clean_hyp = CITE.sub("", hyp).strip()
        if not cited:
            out.append(Verdict(raw_s, [], 0, {}, {}, {}, "uncited"))
            continue

        per_doc, loc = {}, {}
        for cid in cited:
            score, where = entail_maxpool(nli, docs[cid], clean_hyp)
            per_doc[cid], loc[cid] = score, where

        # ALCE recall: does the UNION of cited docs entail the sentence?
        union = Doc("union", " ".join(docs[c].text for c in cited))
        union_score, _ = entail_maxpool(nli, union, clean_hyp)
        recall = int(union_score >= tau)

        # ALCE precision: dᵢ alone entails, OR removing dᵢ breaks entailment
        precise = {}
        for cid in cited:
            alone = per_doc[cid] >= tau
            if len(cited) == 1:
                precise[cid] = alone or recall == 1
                continue
            rest = Doc("rest", " ".join(docs[c].text for c in cited if c != cid))
            rest_score, _ = entail_maxpool(nli, rest, clean_hyp)
            precise[cid] = alone or (recall == 1 and rest_score < tau)

        status = "supported" if recall else "unsupported"
        if nli_contradiction is not None and not recall:
            contra = max(nli_contradiction([(docs[c].text, clean_hyp)])[0] for c in cited)
            if contra >= contradict_tau:
                status = "contradicted"       # louder than 'unsupported': drop the sentence

        out.append(Verdict(raw_s, cited, recall, per_doc, precise, loc, status))
    return out


def report(verdicts: Iterable[Verdict]) -> dict:
    v = list(verdicts)
    n = len(v) or 1
    cites = [(d, p) for x in v for d, p in x.precise.items()]
    return {
        "sentences": len(v),
        "citation_recall": round(sum(x.recall for x in v) / n, 3),
        "citation_precision": round(sum(p for _, p in cites) / (len(cites) or 1), 3),
        "unsupported_rate": round(sum(x.status != "supported" for x in v) / n, 3),
        "uncited_rate": round(sum(x.status == "uncited" for x in v) / n, 3),
        "contradicted": [x.sentence for x in v if x.status == "contradicted"],
    }


def should_abstain(rep: dict, min_recall: float = 0.80) -> bool:
    """Abstention must be a REACHABLE OUTPUT or the pipeline is post-hoc citation
    with extra steps."""
    return rep["citation_recall"] < min_recall or bool(rep["contradicted"])


if __name__ == "__main__":
    docs = {
        "policy/refunds-v2.1": Doc("policy/refunds-v2.1",
            "Scope. This policy applies to all plans. "
            "Refunds are available within 30 days of the invoice date. "
            "Annual plans are pro-rated."),
        "billing/INV-8841": Doc("billing/INV-8841",
            "Invoice INV-8841. Issued 2026-07-11. Plan: monthly. Amount: 49.00 USD."),
        "policy/refunds-v1.4": Doc("policy/refunds-v1.4",
            "Refunds are available within 14 days of the invoice date."),
    }
    answer = ("Refunds are available within 30 days of the invoice date "
              "[policy/refunds-v2.1]. Invoice INV-8841 was issued on 2026-07-11 "
              "[billing/INV-8841]. It is therefore eligible for a full refund "
              "[policy/refunds-v1.4]. Processing takes two business days "
              "[policy/refunds-v2.1].")

    # Stub NLI: lexical overlap. Real: MiniCheck-FT5 / AlignScore / HHEM-2.1-open.
    def stub(pairs):
        out = []
        for premise, hyp in pairs:
            tok = lambda t: set(re.findall(r"[a-z0-9\.]+", t.lower()))
            h, p = tok(hyp), tok(premise)
            out.append(len(h & p) / max(1, len(h)))
        return out

    v = verify(answer, docs, stub, tau=0.75)
    for x in v:
        print(f"[{x.status:12}] r={x.recall} {x.sentence[:66]}")
        for d, s in x.per_doc.items():
            print(f"      {d:24} entail={s:.2f} precise={x.precise[d]} @ {x.best_locator[d][:50]!r}")
    rep = report(v)
    print("\n", rep, "\n abstain:", should_abstain(rep))
```

What the run demonstrates, and what to describe in an interview: the last sentence ("processing takes two business days") is a parametric fact with a real, topically relevant, resolving citation that does not support it — **level 2, the dominant failure mode** — and it is caught, driving citation recall to 0.25 and `should_abstain` to `True`. The third sentence cites the superseded v1.4 policy, which is level 3 and is *not* caught by entailment, only by corpus hygiene. Saying that out loud, unprompted, is the senior signal.

One more thing the run shows, deliberately: the *second* sentence ("Invoice INV-8841 was issued on 2026-07-11") is genuinely supported and the lexical stub still flags it, because token overlap is not entailment and the sentence's surface form differs from the source's ("Issued 2026-07-11"). That is the **false-unsupported** failure mode, and it is what a real checker plus decontextualisation buys you. If you demo this, say so before someone asks.

Lab **`(lab pending)`** swaps in MiniCheck with batched GPU inference, adds citation-constrained decoding over an id grammar, the attribute-first two-pass generator, and a golden-set regression gate on citation recall.

---

## How it's done in production

**Managed grounding.** Bedrock Guardrails contextual grounding returns grounding and relevance scores per response with configurable thresholds and filters over 75% of hallucinated responses on RAG and summarisation workloads; Vertex AI grounding attaches support scores and citation metadata. These are the fastest path to a real signal and they operate at *response* granularity or coarse span granularity, which means they gate but do not tell the user which sentence to distrust. Layer your own sentence-level pass on top if the product shows citations inline.

**Eval harnesses.** RAGAS `faithfulness` decomposes the answer into statements and checks each against the retrieved context, which is claim-level attribution wearing an eval hat; RAGChecker, CiteEval (arXiv:2506.01829), and CiteBench give citation-specific testbeds with human statement-level judgments; the Vectara HHEM leaderboard (regenerated on 7,700+ articles across law, medicine, finance, education, technology) is the public reference for summarisation faithfulness, where frontier models in 2026 sit at roughly **1.0-2.5% hallucination**, down from 3-8% in 2023. Do not read that 1% as your production number: it is short-document summarisation with the source in context, which is the easiest possible grounding task. On the harder FACTS Benchmark Suite (Grounding v2 plus parametric, search, and multimodal), **no model breaks 70% overall and Gemini 3 Pro leads at 68.8%**. That contrast — 1% on easy summarisation, sub-70% on hard grounding — is the number pair to quote when someone claims hallucination is solved.

**What to log per response**, so attribution quality is measurable rather than anecdotal: sentence count, citation recall, citation precision, unsupported-sentence rate, contradiction count, checker model + version, threshold + version, retrieval recall proxy (was the gold doc in top-k on your eval set), and abstention decision. Then run a **human audit of n≈100 sentences per release** — automatic metrics do not transfer, so the human sample is what anchors your automatic number.

### What breaks at scale

| Symptom | Cause | Fix |
|---|---|---|
| Citations resolve, users report "that's not what it says" | Post-hoc citation; relevance mistaken for entailment | Grounded generation + sentence-level NLI gate |
| Fabricated arXiv ids / DOIs / case numbers | Closed-book generation, or soft "cite only these ids" instruction | Citation-constrained decoding over the in-context id set |
| Unsupported rate spikes after a chunker change | Premise windows changed; entailment thresholds were fit to the old chunk length | Re-calibrate `tau` on labelled pairs; treat threshold as versioned artefact |
| Everything flags as unsupported after adding a summariser | Sentences not decontextualised; NLI sees unresolved pronouns → neutral | Decontextualise per response before checking |
| Entailment scores collapse to ~0.5 on long chunks | Long premise; NLI trained on short premises | Split premise into 3-sentence windows and max-pool |
| Assistant cites the superseded policy version | Corpus contains v1.4 and v2.1; retrieval has no recency/validity notion | `effective_from` / `superseded_by` metadata, filter at retrieval, retire old docs |
| Deep-research reports get *less* accurate as they search more | Attention dilution during synthesis (79%→17%, 2→150 tool calls) | Cap sources per section; selective over exhaustive citation; verify per section |
| Verification adds 800ms to p95 | Per-sentence NLI called serially, unbatched, one process | Batch all (premise, hypothesis) pairs in one forward pass; run async and retract |
| Citation precision falls while recall rises | Shotgun citing — 5 docs per sentence | Cap citations per sentence at 2-3; report precision next to recall always |
| Quote in the UI does not appear in the linked doc | Model paraphrased inside the quote field | Verbatim substring check on the quote field; reject the claim if it fails |

---

## Tradeoffs & when NOT to use it

- **Do not ship post-hoc citation.** If the architecture generates first and searches second, the citations are decoration and you have manufactured false verifiability, which is worse than none. This is the one hill to die on in this module.
- **Grounded generation lowers coverage, and that is the cost you must state.** Attribute-first can select nothing, constrained decoding can leave the model unable to phrase a true statement, and coverage drops accordingly. If your product needs an answer to every query, grounded generation will feel like a regression and the honest response is a coverage SLO, not a loosened constraint.
- **Do not sentence-cite creative or synthesis-heavy output.** A strategy memo with `[doc-4]` after every clause is unreadable. Use section-level provenance plus an on-demand "show sources for this paragraph". Inline citation belongs where the reader's job is verification.
- **Do not cite at all when there is exactly one source.** A single-document Q&A assistant should highlight the span in the document viewer, not emit `[doc-1]` twenty times. Citation is disambiguation among sources; with one source it is noise.
- **Entailment is not truth.** AIS is explicitly about "according to *s*". If the corpus is wrong, stale, or internally contradictory, a perfectly attributed answer is a perfectly attributed error. Attribution shifts responsibility to corpus quality — which is a real and desirable shift, but say it rather than letting the interviewer discover it.
- **Verification cost is real and it lands on p95.** Sentence-level NLI on a 20-sentence answer is 20-60 premise/hypothesis pairs plus window expansion; batched on a GPU that is tens of milliseconds, unbatched over HTTP it is hundreds. If you cannot afford it in-path, run it asynchronously and design a UI that can retract — and admit that retraction is a worse experience than latency.
- **Automatic attribution metrics are relative instruments.** 2026 audits show metric-human agreement varies by dataset and construct, so your citation-precision number tracks your own regressions and is not comparable to a paper's or a competitor's. Quoting an internal 0.94 as if it were an absolute is a red flag.
- **More retrieval is not more grounding.** The deep-research finding (79% → 17% fact-check from 2 to 150 tool calls) means dumping 100 sources into synthesis makes attribution worse. Selective citation over exhaustive citation.

---

## Interview questions

### Q1 — What is the difference between a citation that exists and a citation that supports the claim?
**Testing:** whether you know the central distinction, with evidence.
**Answer:** Existence is a *plausibility* property: the id resolves, the domain is right, the page is on-topic. Support is a *faithfulness* property: the cited span entails the sentence. They come apart badly. The 2026 deep-research-agent audit found 12 of 14 models above 94% on link validity and every frontier model above 80% on topical relevance, while fact-check accuracy ran 24% to 77% — so a user clicking a citation gets a working, relevant page whose specific claim is unsupported a third to a half of the time. Liu, Zhang & Liang's 2023 audit of generative search engines found the same shape: only 51.5% of sentences fully supported and 74.5% of citations supporting their sentence. Any dashboard that measures link validity is measuring the thing that is already solved.
**Follow-up trap:** *"How would you measure support at scale?"* — ALCE-style citation recall (does the union of cited docs entail the sentence?) and citation precision (does each cited doc either entail alone or become necessary when removed?), computed with an NLI checker, reported alongside an unsupported-sentence rate. And anchor the automatic number with a human audit of ~100 sentences per release, because attribution metrics have been shown not to transfer across datasets.

### Q2 — Why does post-hoc citation produce confident wrong citations?
**Testing:** the core mechanism of the module.
**Answer:** Because the answer already exists before the search runs, so retrieval is not evidence-gathering, it is evidence-seeking for a fixed conclusion — confirmation bias in software. Then retrieval optimises *similarity*, not entailment, and a chunk discussing the same topic while stating the opposite is embedding-close, because negation barely moves an embedding. Then the instruction "cite your sources" makes citation mandatory, so there is no reachable output meaning "nothing supports this". Then the verifier is the generator, so its errors are perfectly correlated with its claims. And finally the citation token is just a token; nothing in the decoder distinguishes a supported `[3]` from an unsupported one.
**Follow-up trap:** *"So retrieval-then-generate fixes it?"* — only if retrieval *constrains* generation rather than merely preceding it. Putting chunks in context with "cite only these ids" is a soft constraint the model routinely violates by attributing a parametric fact to a present-but-unsupporting id. Real constraint means citation-constrained decoding over the in-context id set, attribute-first extraction so the generator can only see selected spans, and an independent entailment gate with abstention as a live branch.

### Q3 — Define citation recall and citation precision.
**Testing:** whether you know ALCE cold.
**Answer:** For a sentence with cited docs C: recall is 1 if the concatenation of C entails the sentence, else 0 — "is this sentence supported at all by what it cites?" Precision is per-citation: doc *dᵢ* counts as precise if *dᵢ* alone entails the sentence, or if removing *dᵢ* breaks entailment of the remainder — "is each citation pulling its weight?" Report mean recall over sentences, mean precision over citations, and derive the headline unsupported-sentence rate as 1 − mean recall.
**Follow-up trap:** *"Why do you need precision at all if recall is high?"* — because recall is trivially gameable: cite five docs per sentence and recall goes up while the user's ability to check anything goes down. Precision penalises the shotgun. In practice I would also cap citations per sentence at two or three, since a citation list is only useful if a human will actually click it.

### Q4 — Design attribution for a RAG assistant over 40k internal policy documents.
**Testing:** end-to-end design with numbers.
**Answer:** Pipeline: hybrid retrieval (BM25 + dense) → rerank → **attribute-first**, a first pass that extracts only the spans answering the question with their doc ids and character offsets → second pass generating prose from the selected spans only, with the raw chunks removed from context and citation ids emitted under a constrained grammar over the selected id set → sentence-level verification, with each sentence decontextualised, premises split into 3-sentence windows and entailment max-pooled, using MiniCheck-FT5 or HHEM-2.1-open batched in one forward pass → render supported sentences plainly, flag unsupported ones explicitly, drop contradicted ones and log the retrieval conflict → abstain if citation recall for the response is below ~0.8. Locators are character offsets so the UI deep-links and highlights, and the quote field is checked as a verbatim substring, which costs nothing and catches paraphrased-quote fabrication that NLI passes. Corpus side, which is the part people skip: `effective_from` and `superseded_by` metadata with retrieval filtering, because entailment against a superseded policy is a perfectly attributed error. SLOs: unsupported-sentence rate under 5%, citation precision above 0.85, verification p95 under 150ms batched, abstention rate budgeted and monitored.
**Follow-up trap:** *"What does this cost in latency and tokens?"* — attribute-first is a second generation call at roughly 1.4-1.8x total tokens; verification is 20-60 premise/hypothesis pairs for a 20-sentence answer, which is tens of milliseconds batched on a GPU and hundreds of milliseconds if you make individual HTTP calls, so batching is not optional. If p95 cannot absorb it, verify asynchronously and design a UI that can retract a claim, and be explicit that retraction is a worse user experience than the latency you saved.

### Q5 — Your NLI verifier flags 40% of sentences as unsupported and the answers look fine to you. Debug it.
**Testing:** whether you have actually run one of these.
**Answer:** In this order. First, **decontextualisation** — check whether the flagged sentences start with pronouns or lack a subject. An NLI model handed "It was raised to 4.5% in March" returns neutral because the hypothesis is not evaluable, and this is the single most common cause. Second, **premise length** — if you are feeding 1,200-token chunks as premises to a model trained on two-sentence premises, scores drift to neutral across the board; split into overlapping 3-sentence windows and max-pool. Third, **threshold** — 0.5 is not a universal default; label ~200 (claim, chunk) pairs from your own corpus and fit the threshold at your target precision. Fourth, **granularity mismatch** — a sentence containing two claims where only one is supported correctly fails at sentence level, so decompose into atomic claims for the high-stakes surface. Fifth, only then consider that the model actually is unsupported 40% of the time, which does happen.
**Follow-up trap:** *"How do you know your verifier is right?"* — you label. A few hundred hand-labelled pairs, computing the verifier's own precision and recall against human judgment, on your corpus. Without that, tuning the threshold is choosing which errors you cannot see. And because attribution metrics have been shown not to transfer across datasets, that labelled set has to be yours, not a benchmark's.

### Q6 — Attribute-first versus generate-then-verify. Pick one.
**Testing:** architectural judgment, and whether you will commit.
**Answer:** Both, and they solve different failures, but if forced to sequence: **generate-then-verify first**, because it is a bolt-on that immediately gives you the measurement — unsupported rate, precision, recall — and you cannot manage what you cannot measure. Then attribute-first, because verification only *detects*; it does not raise the ceiling. Attribute-first structurally binds each sentence to a selected span so faithfulness improves at the source. The costs are real and opposite: verification adds latency and can only reject, attribute-first adds a generation pass, lowers fluency, and lowers coverage. In a high-stakes product I would ship both and treat coverage loss as the accepted price.
**Follow-up trap:** *"Your fluency scores dropped after attribute-first and the PM wants it reverted."* — quantify the trade before arguing. Show unsupported-sentence rate before and after against the fluency delta, and put the numbers in front of whoever owns the risk. If the domain is low-stakes, reverting is a legitimate business call and I would say so. If it is legal or medical, the fluency loss is the product working, and the right compromise is usually the two-tier UI — clean prose with verification driving the flags rather than the phrasing.

### Q7 — Why does more retrieval sometimes make attribution worse?
**Testing:** whether you read the 2026 evidence.
**Answer:** The PwC deep-research audit ablated search depth and found fact-check accuracy falling monotonically while link validity and relevance stayed above 92%: GPT-5.4 went from 79% at 2 tool calls to 17% at 150. Their explanation is attention dilution during synthesis — more retrieved passages means more opportunity to conflate facts across sources and misattribute. The provider-level pattern points the same way: the models generating the most citations had the *lowest* fact-check accuracy, and the model with the highest fact-check accuracy had a lower task-success rate, i.e. selective citation beat exhaustive citation. This is the same shape as context rot from `T07-context-engineering`: more context, worse attention allocation.
**Follow-up trap:** *"So how many sources should a section cite?"* — verify per section rather than per report, and cap sources per section to what a synthesis step can hold cleanly, on the order of 5-10 rather than 100. Then the honest bit: I would not defend a specific cap from the literature; I would measure citation recall as a function of sources-per-section on my own eval set and pick the knee. The point is that this is a tunable with a measurable optimum, not a "more is better" dial.

### Q8 — A citation passes entailment but the answer is still wrong. How?
**Testing:** level-3 failures, the staff-level ones.
**Answer:** Several ways. The cited document is **superseded** — v1.4 entails the sentence, v2.1 overrides it, and entailment has no notion of validity. The cited span is **cherry-picked** — it is the exception clause, and the rule elsewhere in the document contradicts it. The corpus is **internally inconsistent** and retrieval picked one side silently. Or the source itself is simply **wrong**, and AIS is explicitly about "according to *s*", so attribution says nothing about truth. Fixes are corpus and retrieval fixes, not verification fixes: `effective_from` / `superseded_by` metadata filtered at retrieval, retiring superseded documents from the index, and a contradiction sweep across the retrieved set that surfaces conflict to the user instead of picking a winner.
**Follow-up trap:** *"How would you detect the cherry-picking case automatically?"* — run the NLI checker in the contradiction direction across the *other* retrieved chunks: if any retrieved chunk contradicts the generated sentence at high confidence while another entails it, you have a corpus conflict and the correct output is "your documents disagree, here are both", not a confident answer. It costs another k entailment calls and it is the one check that catches the failure class everyone else ships with.

### Q9 — Which verifier model would you use, and why not just prompt GPT-5?
**Testing:** cost-awareness and whether you know the small-model landscape.
**Answer:** A purpose-built small checker: MiniCheck-FT5 at roughly 770M matches Claude 3 Opus and approaches GPT-4 on LLM-AggreFact at a small fraction of the cost, AlignScore-large is 355M, and HHEM-2.1-open is smaller again while beating several larger models. LettuceDetect is worth calling out because it flags unsupported *spans* rather than emitting a verdict, which is directly better UX. A frontier model as judge is more accurate on genuinely hard entailment and 10-100x the cost, so it belongs in offline eval and adjudication of disagreements, not per sentence in the request path. And if the judge is the same family as the generator, its errors correlate with the generator's, so it under-detects exactly the cases you care about.
**Follow-up trap:** *"Where does the small checker fail?"* — long premises (it was trained on short ones, so split and max-pool), multi-hop claims requiring two chunks combined (union entailment helps but is weaker than a real reasoner), numerical and temporal reasoning, and heavily domain-specific language. The pattern that works is a cascade: small checker on everything, frontier judge only on the band near the threshold, which typically covers a small percentage of sentences.

### Q10 — Does RAG solve hallucination?
**Testing:** whether you will say the unpopular thing with a number.
**Answer:** No, it reduces it. The cleanest public evidence is the Stanford RegLab study of commercial legal research tools: RAG-based products from LexisNexis and Thomson Reuters hallucinated in **17% to 33%** of responses versus 43% for GPT-4 — a genuine reduction, and nowhere near the "100% hallucination-free linked legal citations" being marketed. The 2026 benchmark pair says the same thing: frontier models sit at roughly 1.0-2.5% on Vectara HHEM summarisation, which is the easiest possible grounding task with the source in context, while on the harder FACTS Benchmark Suite no model breaks 70% overall and the leader is at 68.8%. RAG changes *where* the failure lives: from parametric fabrication to mis-attribution, mis-ranking, and stale corpus content.
**Follow-up trap:** *"Then what does get you to production-acceptable?"* — a stack, with grounding as one layer: grounded generation, constrained citation ids, per-sentence entailment gating, abstention when nothing entails, corpus hygiene for supersession, and a human gate on anything irreversible. Ordered by measured effect, that ranking is the subject of `T07-hallucination`, and the honest summary is that no single intervention gets you there.

### Q11 — When would you deliberately not show citations?
**Testing:** whether the "when NOT to" instinct is real.
**Answer:** When there is exactly one source — a single-document assistant should highlight the span in the document viewer rather than emit `[doc-1]` twenty times, since citation is disambiguation among sources and with one source it is noise. When the output is creative or synthesis-heavy, because sentence-level markers in a strategy memo destroy readability; use section-level provenance plus an on-demand sources view. When the claim is drawn from the model's general knowledge and no source is being asserted, where the correct move is to mark it *unsourced* rather than to find a plausible source, which is post-hoc citation by another name. And when you cannot verify — an unverified citation is a false trust signal, so if you cannot afford the entailment gate, either abstain or show sources labelled "consulted" rather than "supporting".
**Follow-up trap:** *"Users are asking for citations on the creative surface. Now what?"* — give them provenance without inline noise: a "sources for this section" affordance, and a diff-style view highlighting which paragraphs are source-backed versus model-composed. The user's real request is usually "help me check this", not "put brackets in my prose". Solve the request, not the literal ask.

### Q12 — How would you verify citations in an agent that browses the live web?
**Testing:** transfer to the deep-research case, which is where he actually works.
**Answer:** Different failure profile, so a different pipeline. The content behind a URL is mutable and may be paywalled or JS-rendered, so first: **snapshot at fetch time**, store the extracted text with a content hash, and verify entailment against the snapshot, not against a re-fetch — otherwise your verification result is not reproducible and a page edit silently invalidates your audit. Second: cite the snapshot id plus the URL plus the retrieval timestamp, since "the page said this on 2026-07-19" is the only claim you can actually support. Third: verify per section during synthesis rather than once at the end, because the audit shows accuracy degrading with search depth. Fourth: cap sources per section and prefer selective over exhaustive citation. Fifth: treat "link works" as a health check for the fetcher, not as an attribution metric, and dashboard the fact-check rate separately so the near-saturated metric cannot mask the failing one.
**Follow-up trap:** *"The page is paywalled and you only have the abstract."* — then the honest attribution is to the abstract, with the claim marked as abstract-only support, and any sentence whose entailment depends on the full text marked unsupported. What you must not do is let the model infer body content from the abstract and cite the article, which is exactly the fabrication mode that gets people sanctioned. This also belongs in the system card as a documented limitation.

### Q13 — Rank attribution interventions by effect per unit of effort.
**Testing:** prioritisation.
**Answer:** 1) **Verbatim quote check** on any quoted span — an exact substring comparison, effectively free, and it catches paraphrased-quote fabrication that NLI passes. 2) **Citation-constrained decoding** over the in-context id set, which structurally eliminates fabricated ids at near-zero cost. 3) **Sentence-level entailment gate** with a small checker, batched, with abstention wired up — the biggest single quality jump and the one that turns citations from decoration into evidence. 4) **Span-level locators** so a human can check in one click, which is a UX change that multiplies the value of everything above it. 5) **Corpus supersession metadata**, which is unglamorous and eliminates a whole class of perfectly-attributed errors. 6) **Attribute-first generation**, higher ceiling, real coverage and fluency cost. 7) **Claim-level atomic decomposition** for the high-stakes surface only, at 3-8x verification cost. Dead last: prompt engineering the model to cite more carefully. It is what everyone tries first and it does not move the fact-check number.
**Follow-up trap:** *"Why is the quote check first when it seems trivial?"* — because it is free, deterministic, and it catches a failure mode that model-based verification systematically misses: NLI will happily entail a paraphrase, so a fabricated "quote" that captures the gist passes entailment and fails a human's eyes immediately. Free deterministic checks that catch what probabilistic checks miss are always first.

---

## Red flags that fail you

- Treating "the link resolves" or "the doc is relevant" as evidence of support.
- Proposing generate-then-search-for-sources as a citation architecture.
- Not knowing citation recall and citation precision, or being unable to explain why precision exists.
- Claiming RAG eliminates hallucination. It reduces it; the Stanford legal study measured 17-33% with RAG.
- Asking the generating model to verify its own citations and calling that verification.
- Feeding 1,500-token chunks to an NLI model and trusting the score.
- Flagging sentences as unsupported without decontextualising them first.
- Reporting an internal citation-precision number as if it were comparable across systems.
- No abstention branch: if "nothing supports this" is not a reachable output, the pipeline is post-hoc citation with extra steps.
- Ignoring document supersession, so the system cites a retired policy version and passes every entailment check.
- Citing more sources per sentence to raise recall.

## Cheat card

```
CITATION LADDER  fabricated → well-formed → resolves → topically relevant → ENTAILED → entailed+located
  PwC 2026 (arXiv:2605.06635): link works 94-100% · relevant 80-96% · FACT CHECK 24-77%
  more search = worse: GPT-5.4 fact check 79% @2 tool calls → 17% @150 (relevance stayed >92%)
  Liu/Zhang/Liang 2023 (2304.09848): 51.5% of sentences fully supported · 74.5% of citations support
  Stanford RegLab legal RAG: Lexis+ 17% · Westlaw AI-AR 33% · GPT-4 43% hallucination

AIS (Rashkin 2021)  x attributable to s iff "According to s, x" is true
   ⇒ attribution ≠ truth. Stale/wrong corpus = perfectly attributed error.

ALCE (Gao 2023)
  citation RECALL(s)    = 1 if concat(cited docs) ⊨ s
  citation PRECISION(d) = d alone ⊨ s  OR  removing d breaks entailment
  headline metric = UNSUPPORTED-SENTENCE RATE = 1 − mean recall
  precision exists because recall is gameable by shotgun citing (cap at 2-3/sentence)

4 FAILURE LEVELS  0 fabricated · 1 wrong locator · 2 RELEVANT-BUT-UNSUPPORTING (dominant)
                  3 supports-but-misleading (superseded / cherry-picked / contradicted)
  levels 0-1 → deterministic checks · 2 → NLI · 3 → corpus hygiene + contradiction sweep

POST-HOC FAILS BECAUSE
  answer precedes search (confirmation bias) · retrieval scores SIMILARITY not entailment
  (negation barely moves an embedding) · "cite your sources" makes citation mandatory so
  "nothing supports this" is unreachable · verifier = generator (correlated errors)

GROUNDED GENERATION, weakest→strongest
  ids-in-context + soft instruction        (routinely violated)
  citation-CONSTRAINED DECODING over in-context id set   kills fabricated ids, ~free
  ATTRIBUTE FIRST then generate (2403.17104)  extract spans → generate from spans ONLY
                                              cost: 2 calls, 1.4-1.8x tokens, ↓fluency, ↓coverage
  structured claims w/ evidence id + quote + VERBATIM SUBSTRING CHECK  (free, catches
                                              paraphrased-quote fabrication NLI passes)
  CEILING: you cannot cite what you did not retrieve → retrieval recall is the ceiling

VERIFICATION ENGINEERING
  granularity: response = useless · SENTENCE = default · atomic claim = 3-8x cost, high stakes
  DECONTEXTUALISE first ("It was raised to 4.5%") or you get false 'unsupported'
  SPLIT long premises into 3-sentence windows + MAX-POOL (NLI trained on short premises)
    → winning window is also your span locator
  thresholds are per-model+per-domain: label ~200 pairs, fit tau, VERSION it
  checkers: MiniCheck-FT5 ~770M (≈Claude 3 Opus on LLM-AggreFact) · AlignScore-large 355M
            HHEM-2.1-open (smallest, strong) · LettuceDetect (flags SPANS) · frontier judge 10-100x
  cascade: small checker everywhere, frontier judge only near the threshold band
  BATCH the pairs — 20 sentences = 20-60 pairs; batched = tens of ms, unbatched = hundreds

BENCHMARK PAIR TO QUOTE  Vectara HHEM 2026 summarisation ≈1.0-2.5% hallucination (easy task,
  7,700+ articles) vs FACTS Benchmark Suite: NO model breaks 70%, Gemini 3 Pro 68.8% (hard)

MANAGED  Bedrock ctx grounding (>75% of hallucinated responses filtered, tunable thresholds)
         Vertex grounding w/ support scores · RAGAS faithfulness · CiteEval/CiteBench
LOG      recall · precision · unsupported rate · contradictions · checker@ver · tau@ver · abstained
         + human audit n≈100 sentences per release (auto metrics don't transfer, 2606.23915)
ORDER OF WORK  quote check → constrained ids → NLI gate + abstain → span locators →
               supersession metadata → attribute-first → atomic claims
```

## Sources

- [Cited but Not Verified: Parsing and Evaluating Source Attribution in LLM Deep Research Agents (arXiv:2605.06635)](https://arxiv.org/html/2605.06635v1) — accessed 2026-07-26
- [Evaluating Verifiability in Generative Search Engines (Liu, Zhang & Liang, arXiv:2304.09848)](https://arxiv.org/pdf/2304.09848) — accessed 2026-07-26
- [Hallucination-Free? Assessing the Reliability of Leading AI Legal Research Tools (Magesh et al., J. Empirical Legal Studies 2025)](https://onlinelibrary.wiley.com/doi/full/10.1111/jels.12413) — accessed 2026-07-26
- [Attribute First, then Generate: Locally-attributable Grounded Text Generation (arXiv:2403.17104)](https://arxiv.org/html/2403.17104v2) — accessed 2026-07-26
- [Explicit Evidence Grounding via Structured Inline Citation Generation (arXiv:2606.07130)](https://arxiv.org/abs/2606.07130) — accessed 2026-07-26
- [CiteEval: Principle-Driven Citation Evaluation for Source Attribution (arXiv:2506.01829)](https://arxiv.org/html/2506.01829) — accessed 2026-07-26
- [Do LLM Attribution Metrics Transfer? Auditing RAG Evaluation Across Datasets and Constructs (arXiv:2606.23915)](https://arxiv.org/html/2606.23915v1) — accessed 2026-07-26
- [Relevant Is Not Warranted: Evidence-Force Calibration for Cited RAG (arXiv:2605.28044)](https://arxiv.org/html/2605.28044) — accessed 2026-07-26
- [MiniCheck: Efficient Fact-Checking of LLMs on Grounding Documents (arXiv:2404.10774)](https://arxiv.org/pdf/2404.10774) — accessed 2026-07-26
- [Benchmarking LLM Faithfulness in RAG with Evolving Leaderboards (arXiv:2505.04847)](https://arxiv.org/html/2505.04847v2) — accessed 2026-07-26
- [Model Internals-based Answer Attribution for Trustworthy RAG (MIRAGE, arXiv:2406.13663)](https://arxiv.org/pdf/2406.13663) — accessed 2026-07-26
- [Introducing the Next Generation of Vectara's Hallucination Leaderboard](https://www.vectara.com/blog/introducing-the-next-generation-of-vectaras-hallucination-leaderboard) — accessed 2026-07-26
- [AI Model Hallucination Rates 2026: Vectara HHEM & AA-Omniscience Rankings](https://codingfleet.com/blog/ai-model-hallucination-rates-2026/) — accessed 2026-07-26
- [Amazon Bedrock Guardrails — contextual grounding checks](https://aws.amazon.com/bedrock/guardrails/) — accessed 2026-07-26

## Changelog
- 2026-07-26 — created
