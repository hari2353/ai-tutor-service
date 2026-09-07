# Production notes — hallucination detection

## What you'd actually use

| Detector | How it works | Numbers to quote | Cost |
|---|---|---|---|
| **SelfCheckGPT** (self-consistency) | sample n stochastic generations, score each answer sentence by agreement (BERTScore / NLI / prompt) | AUC-PR ~0.53–0.67, ~0.58 AUROC on hard sets | n× generation cost — 20 samples in the original paper |
| **NLI / grounding verification** | small entailment model scores each decontextualised sentence against 3-sentence context windows, max-pooled | MiniCheck-FT5 (~770M) ≈ Claude 3 Opus on LLM-AggreFact; Bedrock contextual grounding filters >75% of hallucinated RAG responses | tens of ms batched; hundreds unbatched |
| **RAGAS hallucination** (manager-free variant) | per-claim: does any context sentence entail it, judged by a cheap LLM | fits the extracted/inferred/unsupported shape you just built | an LLM call per claim — judge costs dominate |
| **Semantic entropy** (Farquhar et al., Nature 2024) | cluster n samples into meaning classes by bidirectional entailment, entropy over classes | ~0.60 AUROC on hard sets | O(n²·|C|) NLI calls |

Your lexical/numeric/entity checker is the deterministic floor under all of these: it catches fabricated numbers, invented entities, and copied-with-a-swap sentences at zero cost, and it is fully reproducible. The real systems run something like it as a cheap first pass and escalate the ambiguous spans to NLI or a judge.

## Why grounding-to-context (not truth) is the right bar

Three reasons, and the order matters:

1. **It is testable with the source in hand.** You have the retrieved chunks; you do not have the world. Faithfulness failures are decidable by inspection *today*; factuality failures need an external KB and become a fact-checking product.
2. **It localises the fix.** An ungrounded span means one of two things: retrieval missed the right chunk, or the model went beyond it. Both are *your pipeline's* failure, both diagnosable from the trace, both fixable (better retrieval / constrained generation / abstention). "False in the world" tells you nothing actionable about your system.
3. **It matches the deployment contract.** A grounded RAG answer that is wrong is a retrieval bug you can test. A correct answer the context does not support ("the Eiffel Tower is in Paris") is a lucky guess that will be a fabrication tomorrow — the model had no basis, and the basis is what you are auditing.

This is also why the bar is *the* cited distinction in the module: faithfulness is tractable and where 90% of the engineering effort goes; factuality is not.

## The "true fact not in context" trap

The case that catches everyone: "The Eiffel Tower is in Paris" is *true*, your detector calls it *unsupported*, and someone files it as a false positive. It is not — it is the detector working exactly as specified. The answer had no basis in the retrieved context, and shipping it means shipping model parameters as the source of record. The right product behaviour is: route that span to retrieval-again or abstention, not "let it through because a human knows it's true". Kalai & Vempala (STOC 2024) is the theory behind the intuition: a calibrated model must hallucinate arbitrary facts at a rate bounded below by the monofact rate — confident truth with no basis is not an anomaly to whitelist, it is the failure mode itself. The inverse trap is symmetrical and worse: "founded in 1999" is 80%+ verbatim overlap with a real sentence and sails through any pure-overlap check — which is why numbers and entities gate the extracted class in this lab, and why pure lexical detectors (SelfCheckGPT's n-gram variant) bottom out near 0.53 AUC-PR while NLI grounding beats them.

## What breaks at scale

| Symptom | Cause | Fix |
|---|---|---|
| Verbatim-entailment miss on "50" vs "fifty" | no normalisation | number-word mapping before the check |
| Whole-sentence NLI misses a one-word fabrication | sentence-level granularity | span-level (LettuceDetect does spans; "which sentence" is actionable, "0.31" is not) |
| Detector passes an answer that contradicts a *different* chunk than the cited one | checking against the whole context, not the citations | check per-citation for attributed answers (Lab 24 attribution) |
| Latency blowup at verification | per-sentence HTTP calls to the NLI | batch; or verify asynchronously and accept retraction UX |
| Grounding score high, answer still wrong | retrieval recall — the right chunk was never fetched | the failure is upstream: fix retrieval, don't tune the detector |

## The 3 questions an interviewer asks after you describe this

1. *"Your grounding checker passed a true fact as unsupported — is it broken?"* — No: grounding is against the context, not the world. It flags missing *basis*, which is the only thing your pipeline owns. Escalate to retrieval or abstain; do not whitelist by human knowledge.
2. *"Why not just use an LLM judge for all of this?"* — as the primary, cost and non-determinism (plus the judge's own hallucination rate); as the second pass after the deterministic floor, fine — that is roughly the RAGAS shape.
3. *"Where does this run in an agent loop?"* — on the observation path (before tool output enters context) and the action path (before side effects), not just on the final answer; a fabricated intermediate becomes the premise of step 7 and by then it is load-bearing.
