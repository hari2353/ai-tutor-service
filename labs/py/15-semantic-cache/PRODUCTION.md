# Production notes — semantic caching

## What you'd actually use

| Concern | Off-the-shelf | Note |
|---|---|---|
| Semantic cache | GPTCache (Zilliz) | pluggable embedding/vector-store/evaluator/eviction — the reference architecture |
| Managed cache | RedisVL semantic caching | vector similarity + hard metadata filters in the query itself |
| Prefix/prompt caching | Anthropic `cache_control`, OpenAI automatic prefix caching | KV-tensor reuse, byte-identical prefix required, zero correctness risk |
| Adaptive thresholds | vCache (arXiv:2502.03771) | per-entry online-learned threshold with a formal error-rate bound |

## What the real ones add over yours

- **Embeddings, not trigrams** — char-3gram Jaccard is a teaching proxy; production uses embedding cosine + ANN (`03-vector-index-internals`). The layer *interface* survives the swap; the false-hit profile changes completely.
- **Similarity evaluator as a separate decision function** — GPTCache separates the raw score from the hit decision so an ONNX cross-encoder can veto high-similarity false hits.
- **Hard namespace filters in the lookup** — tenant/locale/model version enforced inside the query, never post-hoc on whatever the ANN search returned. Your lab scopes by model for exactly this reason.
- **Invalidation wired to the corpus pipeline** — event-driven entry invalidation or versioned namespaces, not TTL alone.
- **Positive hit rate reported next to hit rate** — 60% hit rate means nothing until you know what fraction of those hits were correct.

## What breaks at scale

| Symptom | Cause | Fix |
|---|---|---|
| Confidently wrong answers at cache speed | False hits: pair differs in exactly the token that matters (date/tier/polarity) yet clears the threshold | Tighten per cluster, add a verification step, or go adaptive (vCache-style) |
| Hit rate collapses toward zero | Threshold set conservatively for everything | Tune per query cluster; report hit-rate-per-threshold curves, not one number |
| Tenant B's data shows up in tenant A's answer | Shared semantic namespace across tenants | Hard tenant filter inside the lookup; treat the cache as an attack surface |
| Answers stay wrong after a document fix | No invalidation path tied to corpus change | Event-driven invalidation or versioned cache namespaces |
| Prefix cache near-zero hit rate despite stable system prompt | Volatile content (timestamp, UUID) before the breakpoint | Move volatile bytes after the breakpoint; prefix must be byte-identical |
| Memory grows without bound | Entries never expire and capacity is unbounded | TTL + capacity cap with observable eviction counters — the boring half of this lab |

## Cost & latency

The worked math from the curriculum holds because hit cost (~embedding call) is negligible next to an LLM call: at $0.003/call, 1M queries/day, 40% hit rate → ~39% cost reduction, and blended p50 tracks the hit rate almost linearly. That arithmetic is also why one false-hit percentage point is expensive: it is invisible in latency dashboards and only shows up in complaint volume.

## The 3 questions an interviewer asks after you describe this

1. *"Isn't prefix caching just weak semantic caching?"* — no: it requires a byte-identical shared prefix, carries zero correctness risk, and does nothing for paraphrases. Conflating them is the classic red flag.
2. *"Your threshold is 0.92. Why?"* — if the answer is "it seemed reasonable," that's the fail; the threshold is a correctness boundary to be validated against false-positive measurements, not a perf knob.
3. *"Same prompt, different model — hit or miss?"* — miss, always: model identity is part of every layer's namespace, because answers legitimately differ per model.
