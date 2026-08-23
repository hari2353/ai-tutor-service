# Production notes — RAG evaluation

## What you'd actually use

| Need | Tool |
|---|---|
| Four-metric decomposition + synthetic testsets | RAGAS |
| Pytest-native eval in CI | DeepEval (Confident AI) |
| Tracing + span-level scoring (which chunk, which prompt) | TruLens, Arize Phoenix, LangSmith evals |
| Config-as-code eval gates in PRs | promptfoo |

Your lab's `JudgeStub` is the seam where these plug their real LLM judges.

## What the real ones add over yours

- **A real judge behind the seam** — an actual model doing relevance/support/attribution calls, which is why everything below matters and your keyword stub doesn't.
- **Embedding-based relevancy** — answer relevancy via reverse-generated questions + embedding similarity, not term overlap; catches paraphrases your lexical stub never would.
- **Claim decomposition by LLM** — answers split into atomic claims semantically, not on sentence punctuation.
- **Testset generation with question evolution** — generated questions deliberately paraphrased away from source-chunk vocabulary, with difficulty controls (single-hop / multi-hop / conditional).
- **Regression tracking over time** — baselines, dashboards, per-metric drift alerts instead of one-off report dicts.

## What breaks at scale

| Symptom | Cause | Fix |
|---|---|---|
| Eval costs more than the pipeline it guards | 4+ LLM judge calls × N examples × every commit | Cache judge results keyed on input hash; sample the suite; full run nightly only |
| Scores move between identical runs | Judge temperature > 0, provider-side nondeterminism | temp 0 for gating runs; average multiple calls; pin judge model version |
| Judge upgrade silently shifts every metric | Scoring distribution is judge-relative | Re-run calibration against the human-labeled subset after ANY judge-model change |
| Blended "answer quality" score improved, users disagree | Retrieval regression hidden inside the blend | Gate on context recall/precision separately — never on one number |
| Synthetic set scores near-perfect, production doesn't | Generated questions reuse source-chunk vocabulary → trivially retrievable | Question-evolution steps + human-reviewed holdout subset |
| Faithfulness fine, answers still wrong | Faithful to WRONG context — retrieval surfaced plausible-but-bad chunks | Check recall/precision on the same cases; faithful ≠ correct |

## Cost & latency

The stub judge is microseconds. A real judge is the dominant eval cost: budget roughly 1 call per retrieved chunk (precision) + 1 per ground-truth sentence (recall) + 2 per case (faithfulness claims, relevancy). That multiplies fast at thousands of cases × every PR — hence caching, sampling, and reserving full sweeps for scheduled runs.

## The 3 questions an interviewer asks after you describe this

1. *"Why four metrics instead of one score?"* — attribution. Each metric isolates one independently-fixable subsystem; a blend turns every regression into a guessing game.
2. *"How do you trust the judge?"* — you don't, absolutely. Calibrate against a human-labeled subset (~hundreds of examples), re-calibrate whenever the judge model changes, and treat judge output as directionally reliable at best.
3. *"High context recall but low faithfulness — what does that mean?"* — the clearest hallucination signal there is: the right evidence was retrieved and the generator said something it doesn't support. The fix is in the generation prompt/model, not retrieval.
