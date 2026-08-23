# 20 GenAI/Agent Designs (RAG@10M, LLM gateway, agent platform)

> Sprint weekend 9 · source: `curriculum/10-system-design/07-genai-designs.md`

```
THE SIX SLOTS (every design, every time)
  1 CLARIFY (6 min)  what the number MEANS · read:write · latency · tenant · "correct"
  2 ARCHITECT (10)   write path and read path drawn SEPARATELY
  3 DECIDE (12)      3-5 forks as "X over Y because Z, at the cost of W"
  4 SIZE (6)         QPS · bytes · tokens → $/request → $/month.  UNPROMPTED.
  5 BREAK (6)        failure → OBSERVABLE SYMPTOM → mitigation
  6 DEFEND (5)       the 3 hardest follow-ups, answered first

WHAT MAKES GENAI DIFFERENT (and what doesn't)
  PROBABILISTIC → eval is a COMPONENT · EXPENSIVE $0.01-0.30/req → cost model is
  ARCHITECTURE · SLOW 1-10 s → streaming/caching/step-reduction are architecture
  UNCHANGED: backpressure · hot shards · idempotency · migrations · noisy neighbours

7 RECURRING PATTERNS
  1 write path != read path        2 TWO-STAGE retrieval is universal
    (binary→full · vector→reranker · graph→vector · cheap model→strong)
  3 enforcement boundary must be UNBYPASSABLE (gateway+netpol, perms engine, index predicates)
  4 version everything behaviour-changing, put it ON THE TRACE
  5 $/request out loud, then $/month, then lever ordering
  6 every failure needs an OBSERVABLE symptom
  7 FILTER (classifier, label, prompt) vs BOUNDARY (perms, netpol, sandbox). Never conflate.

KEY NUMBERS
  pgvector vs dedicated engine boundary          ~5-10M vectors
  1024-dim: fp16 2 KB · int8 1 KB · binary 128 B → 100M vectors = 200 GB / 100 GB / 12.8 GB
  AWS S3 Vectors: 10M vec + 1M q/mo = $11.38 · 500M + 10M = ~$1,320 (100s of ms latency)
  RRF fusion default k=60 · rerank 150→8 ~85 ms on a shared T4
  semantic cache HONEST hit rate 20-45% (30-70% FAQ); threshold ~0.83 MPNet / ~0.78 Albert;
    GPTCache default 0.7 is TOO LOOSE; start 0.92 and tune down 0.01/step
  RouteLLM 95% of GPT-4 quality @ 26% strong calls, ~48% cheaper than random;
    75% cut with judge-augmented data; prod reports 40-85% (plan for 40-50%)
  outcome-only evals pass 20-40% MORE cases than trajectory evals → they overstate readiness
  gen_ai.* OTel conventions: own repo since v1.42.0 (2026-06-12), still DEVELOPMENT → pin
  support deflection: 2026 median 41.2%, top quartile 58.7%; resets >70%, complaints <25%
    pure-AI CSAT 4.1/5 vs human 4.3/5; hybrid handoff narrows to ~0.05
  doc pipeline per page: text layer $0.0002 · OCR $0.0015 · VLM $0.006 → router = 5x saving
  code index: 40M LOC → ~1.2M chunks ≈ 0.9 GB (small!). Graph is the expensive part.
    tree-sitter graph over 31 repos: ~10x fewer tokens, ~2.1x fewer tool calls
  self-host breakeven: 8B on 2xA10G ~$1.5k/mo beats a commercial small model only
    above ~40-50% SUSTAINED utilisation
  canary detection floor: 3 pp judge delta needs n≈400 scored → 5% of 8k/day = ONE DAY
  guardrail FP budget: at 900 rps, 1% false-block = 780k legit requests/day. Target <0.2%.

THE 12, BY THEIR ONE DECISION
  1 RAG 10M    quantized 1st stage + rescore; ACLs INTO the index
  2 gateway    in-path proxy + network egress denial (~1% of spend it governs)
  3 orch       control/data plane split; eval-gated registration; hierarchical budgets
  4 memory     typed bi-temporal facts, async write; EXTRACTION is the cost (~$28k/mo)
  5 eval       one dataset store for CI + prod; deterministic before judges
  6 prompts    immutable content-addressed; rollback = POINTER FLIP
  7 cache      key = (query, tenant, corpus_ver, model, prompt_hash). Cache RETRIEVAL if unsure.
  8 guardrail  parallel detectors; input rail CONCURRENT with retrieval; FP rate is the cost
  9 docs       adaptive per-page routing (5x); tables ATOMIC; keep originals + versioned IR
 10 support    explicit escalation triggers + STRUCTURED handoff; never optimise deflection alone
 11 code       3 latency tiers, 3 context strategies; TESTS are the verifier
 12 router     tiered L0-L4; measure $/COMPLETED TASK, not per token

WHEN NOT TO
  RAG under ~50-100k tokens of stable content → cached prefix
  dedicated vector DB under ~5-10M vectors → pgvector
  gateway under ~$10-20k/mo → not yet
  platform under 5-10 agents → build 3 good services
  cross-session memory in v1 → earn it with a re-derivation rate
  semantic cache on low-repetition or auth-dependent answers → decline
  guardrails AS the security story → it's a filter with a false-negative rate
  router before bill attribution → you're guessing, with quality risk attached
```
