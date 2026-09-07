# Production notes — attribution

## What you'd actually use

| Need | Use |
|---|---|
| Faithfulness metric | RAGAS `faithfulness` (decompose answer into claims, verify each against retrieved context) |
| Citation eval | ALCE citation recall/precision · CiteEval · CiteBench |
| Small NLI checkers | MiniCheck-FT5 (~770M, matches Claude 3 Opus on LLM-AggreFact) · AlignScore-large (355M) · HHEM-2.1-open (smallest) · LettuceDetect (flags spans, not verdicts) |
| Managed grounding | Bedrock Guardrails contextual grounding (tunable thresholds, filters >75% of hallucinated responses on RAG workloads) · Vertex AI grounding support scores |

Your overlap classifier is the lexical ancestor of all of these: RAGAS faithfulness is claim-level attribution wearing an eval hat, ALCE recall is your SUPPORTED verdict with an NLI scoring the overlap, and your numeric gate is the deterministic check that survives model-free.

## What RAGAS faithfulness actually does, internally

1. A decomposer LLM rewrites the answer into short standalone claims (decontextualised — pronouns resolved, subjects restored). Your lab skips this by taking claims as input; in production, this step is where the metric's variance lives.
2. For each claim, an NLI/verifier scores the claim against the retrieved context. RAGAS defaults to an LLM judge prompting "is this claim supported by the context?"; swapping in MiniCheck or HHEM makes it cheap enough for CI.
3. Faithfulness = supported claims / total claims — exactly your `faithfulness_score`. The decompose-then-average shape means one flaky claim can flip the verdict on a good answer, so the decomposer prompt is versioned like any other model artefact.

## Citation grounding in production RAG

**Inline spans vs end citations.** Three production shapes, in rising order of verifiability:

- **End-of-answer source list** — "consulted" sources; no claim binding. Weakest; you built the tool that shows why.
- **Per-sentence endnote markers** `[1][2]` — binds claim to doc, but the user must hunt the sentence in the page. This is what your `CitedAnswer` models.
- **Inline span citations with locators** — `{"doc", "locator": "chars 400-460", "quote"}` per claim, quote checked verbatim. The deep-link-with-highlight that is becoming table stakes.

Production RAG (Bing/Perplexity-style search assistants, enterprise policy assistants) mostly ships per-sentence endnotes; the 2026 direction is span-level locators because a citation you cannot check in one click is a decoration. Note the trade: inline spans are honest but unreadable in synthesis-heavy prose — use section-level provenance there instead.

**How citations are generated matters more than how they are verified.** Post-hoc citation (generate from weights, then search for sources that look like they agree) is a confirmation-bias machine: retrieval optimises similarity, not entailment, and "cite your sources" makes citation mandatory, so "nothing supports this" is unreachable. Grounded generation (attribute first, then generate from selected spans) makes every sentence bound to a span by construction. Your construction-time validation — unknown id → `ValueError` — is the structural ancestor of citation-constrained decoding over an id grammar, which kills fabricated ids at near-zero cost.

## What auditor-mode evals add over in-path verification

In-path verification gates one response at p95 cost. Auditor-mode evals run the same checks offline, over datasets, and add what in-path cannot:

- **Rates, not verdicts** — unsupported-sentence rate across a golden set becomes a release gate and a regression signal. In-path gives you one answer's score; the auditor gives you a distribution.
- **Transfer honesty** — attribution metrics do not transfer across datasets (arXiv:2606.23915), so your internal number is a relative instrument. An auditor run on a public benchmark (LLM-AggreFact, CiteEval) plus ~100 human-checked sentences per release is what anchors it.
- **Failure taxonomy** — the auditor bins misses into fabricated / wrong-locator / relevant-but-unsupporting / superseded, which tells you *which fix* (constrained decoding, span locators, NLI gate, corpus hygiene) moves the number. A single faithfulness score cannot.
- **Threshold calibration** — 0.60 overlap here, NLI `tau` in production: both are per-model, per-domain, and must be fit on ~200 hand-labelled pairs from your own corpus and versioned like code.

## The 3 questions an interviewer asks after you describe this

1. *"Your verifier scores 0.94 faithfulness. Is the answer 94% correct?"* — No. Faithfulness means supported-by-cited-context (AIS: "according to s"), not true. If the corpus is stale or internally contradictory, a perfectly attributed answer is a perfectly attributed error. Corpus supersession metadata is the fix, and it is a corpus fix, not a verification fix.
2. *"Why does the numeric mismatch case get its own gate instead of just being low overlap?"* — because lexical overlap is blind to it: "30 days" and "90 days" share every word but the number. Numbers are the cheapest deterministic entailment there is — a set-membership check that no embedding similarity can fake, which is why the quote-check family always runs before the model-based checks.
3. *"Where does your wrong-citation test land in the wild?"* — the dominant failure mode: 2026 deep-research audits found link validity at 94-100% and topical relevance above 80% while fact-check accuracy ran 24-77%. Your test 3 is that gap in miniature — the right vocabulary, the wrong document — and "similarity is not entailment" is the sentence to say in the interview.
