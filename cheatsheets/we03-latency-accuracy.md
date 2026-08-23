# The Latency/Accuracy/Cost Triangle: Where to Spend, What to Cut

> Sprint weekend 3 · source: `curriculum/06-rag/15-latency-accuracy.md`

```
2s BUDGET (worked example)     embed ~75ms · ANN ~100ms · rerank ~250ms (top~100) · buffer ~75ms
                                → generation gets ~1500ms (~75% of total) — dominates, least controllable

STAGE LATENCIES (starting points — validate against your own p50/p99)
  query embedding      50-100ms   (Voyage lite ~52ms/query)
  ANN retrieval        50-150ms   (depends on corpus size + filter selectivity)
  cross-encoder rerank 100-300ms  (Cohere API) · ~50ms/pair self-hosted BGE-v2-m3 on GPU
  generation           remaining budget — dominant, least compressible without model/output-length change

CASCADE PATTERN   stage1 WIDE+CHEAP (hybrid ANN, top 50-150, optimizes RECALL)
                  → stage2 NARROW+EXPENSIVE (cross-encoder, top 3-20, optimizes PRECISION)
                  works because stage1 cost ~flat vs top-k; stage2 cost scales linearly w/ top-k

RECALL COST       extra candidates cost: (1) reranker $/latency, linear in count
                  (2) generation context tokens, linear in count+size
                  (3) quality — "lost in the middle" past a threshold: MORE CONTEXT CAN HURT

CUT RERANKING WHEN   stage-1 recall already sufficient (eval-verified) · budget <500ms end-to-end
                     · corpus small/low-noise · cost at your QPS doesn't pencil out

STACKING            hybrid + contextual-retrieval + rerank + reformulation: NOT additive in accuracy,
                    IS additive in latency. Measure marginal gain of each addition before keeping it.

DECIDE WITH DATA    offline eval (recall@k/nDCG) gates → shadow/canary for real p50/p99 →
                    online A/B on user-facing metric (task success, not just recall@k) → ship

COST                Cohere rerank: $0.001-0.0025/search (≤100 docs, >500-tok docs split & rebilled)
                    self-host (BGE) crossover point exists at some QPS — compute it, don't guess
```
