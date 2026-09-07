# Lab 25: Hallucination — Taxonomy and Detection

**Track:** T07 Agentic AI · **Time:** 2.5h · **XP:** 50
**Module:** `T07-hallucination`

**You will build:** a span-level hallucination classifier that labels every sentence of an answer `extracted`, `inferred`, or `unsupported` against the retrieved context — lexical overlap, numeric consistency with single-step arithmetic derivation, and entity grounding, in pure stdlib.

**You will be able to answer:** *"How do you actually detect hallucinations in a RAG pipeline — and why do you ground against the context rather than against the world?"*

## Setup

```bash
cd labs/py/25-hallucination
python -m venv .venv && . .venv/bin/activate     # or: uv venv && . .venv/bin/activate
pip install pytest                                # only dependency
```

## The spec

Rule zero, before any of the numbered ones: **grounding is against the provided context, not against the world.** "The Eiffel Tower is in Paris" scored against a context that never mentions Paris is *unsupported* — true, but ungrounded. That is not a bug; it is the entire design (see PRODUCTION.md).

1. **Content words** — lowercase tokens, `len >= 3`, minus the stopword list in the starter. Numbers with 3+ digits count as content words; short numbers (`50`) do not — numbers are judged by rule 3, never by overlap.
2. **`classify_span(span, context_docs)`** → `"extracted"` (≥ 80% of content words appear verbatim in the context, and numbers/entities check out — a copied sentence with one swapped number is *not* extracted), `"inferred"` (numbers consistent + entities grounded + overlap ≥ 40%), or `"unsupported"` (otherwise).
3. **`numeric_consistency(span, context)` → `(ok, reason)`** — every number in the span must appear in the context OR be derivable via a **single** arithmetic step (`+` or `-`) from two numbers both present. "founded 27 years before 2025" is fine when 1998 and 2025 are in context (2025 − 1998 = 27). Two-step derivations must fail. The reason names the offending number.
4. **`entity_grounding(span, context)` → `(ok, missing_entities)`** — every capitalized multi-word run or known-entity-like token (capitalized words *not* at sentence start, or all-caps like `RAG`) must appear in the context. Consecutive capitalized words group into one entity ("Eiffel Tower"). Sentence-start capitals are skipped on purpose — that ambiguity is the classic NER hard case, and the spec chooses to miss "Acme" at position 0 rather than flag every sentence.
5. **`detect(answer, context_docs)`** — sentence-split the answer, classify each span, and return `{"spans": [{"span", "class"}], "unsupported_fraction"}`.

## Run the tests

```bash
python -m pytest tests -q                # against starter/ → FAILS. Make them pass.
```

To check the reference: `python -m pytest tests -q --solution`

## Stretch goals

1. **Contradiction vs silence** — split `unsupported` into intrinsic (a context number contradicts the span) and extrinsic (context is silent). *(Interview: "walk me through the faithfulness/factuality 2×2.")*
2. **NLI upgrade** — swap lexical overlap for an injectable `nli(premise, hypothesis) -> float` callback, scored over 3-sentence context windows with max-pooling. *(Interview: "when does lexical overlap lie?")*
3. **Cite-then-verify** — attach the supporting doc index to every `extracted` span. *(Interview: "attribution vs hallucination — the same check?")*
4. **Abstention policy** — map the report to drop/flag/abstain decisions per the module's ranking, with a tunable `unsupported_fraction` threshold. *(Interview: "where does abstention beat verification?")*
