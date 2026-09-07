# Lab 24: Attribution — Citations That Hold Up

**Track:** T07 Agentic AI · **Time:** 2.5h · **XP:** 50
**Module:** `T07-attribution`

**You will build:** a citation verifier that splits an answer into claims, checks each claim against the sources it *actually cites*, flags wrong-citation and fabricated-number claims, and reduces the answer to one faithfulness score.

**You will be able to answer:** *"Your citation resolves and the page is on-topic. How do you know it supports the claim — and what does 'faithfulness' even measure?"*

## Setup

```bash
cd labs/py/24-attribution
python -m venv .venv && . .venv/bin/activate     # or: uv venv && . .venv/bin/activate
pip install pytest                                # only dependency
```

## The spec

`attribution.py` — one file, pure stdlib. The stopwords list, status names, and the 0.60 / 0.20 thresholds are given constants; the tests are calibrated to them exactly.

1. **`CitedAnswer(claims, sources)`** — claims are `{"text": str, "source_ids": list[str]}`; sources are `{source_id: source_text}`. Validates **at construction**: every claim must cite at least one id that canonicalizes to a known source. Unknown id → `ValueError`. This is the cheap ancestor of citation-constrained decoding: a fabricated id never enters the answer object.
2. **`verify(answer, sources) -> report`** — for each claim, compute `overlap = |content_words(claim) ∩ content_words(union of cited sources)| / |content_words(claim)|`, then classify:
   - **SUPPORTED** — overlap ≥ 0.60 **and** every number in the claim appears in the union of cited sources.
   - **PLAUSIBLE_UNSUPPORTED** — 0.20 ≤ overlap < 0.60. On topic, never stated — the dominant real-world citation failure.
   - **FABRICATED** — overlap < 0.20, **or** a ≥0.60-overlap claim whose numbers are absent, with reason `"numeric mismatch: ..."`.
   - Content words: lowercase alpha-only words of length ≥ 3, minus the stopword list. Numbers are **not** content words — they get their own gate, because lexical overlap is blind to "30 days" vs "90 days".
   - The report is a dict: `{"claims": [{"text", "source_ids", "status", "overlap", "reasons"}, ...], "total", "supported", "plausible_unsupported", "fabricated", "faithfulness"}`.
   - **The one rule that matters: classify against the sources the claim cites, never the whole corpus.** A correct fact cited to the wrong document is a citation failure even when another document supports it.
3. **`faithfulness_score(report)`** — fraction SUPPORTED (RAGAS faithfulness, lexical edition). Empty report → 1.0.
4. **`normalize_citations(answer)`** — dedupe near-identical ids ("doc1", "doc1 ", "Doc1#sec2" are one citation: strip, lowercase, cut at `#`) and sort citations canonically. Returns a **new** `CitedAnswer` validated against the same sources, so normalization can never smuggle in an unknown id.

## Run the tests

```bash
pytest tests/ -q                 # against starter/ → FAILS. Make them pass.
pytest tests/ -q --solution      # the reference — must be green
```

## Stretch goals

1. **ALCE precision** — per cited doc: precise if it entails the claim alone *or* removing it breaks support. *(Interview: "citation recall vs citation precision — why does precision exist?")*
2. **Per-source attribution** — attribute each content word to the specific doc that contributed it, so the report can say *which* citation is doing the work. *(Interview: "what do you log per response so attribution quality is measurable?")*
3. **Injectable NLI** — make the overlap gate a callable so a stub NLI or a real checker (MiniCheck, HHEM) can be swapped in without touching the tests. *(Interview: "why not just prompt GPT-5 to check?")*
4. **Abstention** — a `should_abstain(report, min_faithfulness)` gate so "nothing here is supported" is a reachable output, not a silent shrug. *(Interview: "when is not answering the right answer?")*
