# Weekend 9 — Shipping Agents to Production and GenAI System Design

This weekend decides interviews because it's where everything from earlier weekends gets assembled under a deadline — "how would you actually ship this" and "design me a GenAI system" both punish people who know the pieces but have never had to sequence them against a budget, a gate, and a rollback plan.

## Zero → Production: The Complete Multi-Agent System, End to End

**30-sec:** Shipping an agent is 15% agent and 85% platform, and the 85% is what gets interviewed. Scope to the narrowest task with a verifiable success signal, start with one agent (multi-agent is a cost you must earn), put the loop inside a durable graph with a Postgres checkpointer so both a day-long approval and a pod eviction resume rather than restart, and wrap it in a harness owning budgets, permissions, provenance, compaction, and structured output. Build the two things nobody builds in a POC and everyone needs in production: a golden-trajectory eval suite as a blocking CI gate, and OTel traces plus a per-session cost ledger — cost silently drifts 3–4× between POC estimate and production reality without them.

**Three state boundaries own every hard problem:** model boundary is stateless (context rebuilt each turn, cost quadratic in turns) · process boundary is unreliable (durable state belongs in Postgres, not Python) · trust boundary is porous (label provenance, bound damage in code, not in a prompt).

**Scoping, six answers before code:** unit of work, verifiable success signal, blast radius, latency contract, cost ceiling per unit, principal *and* tenant (two separate axes — conflating them is a security leak). Write the non-goals down.

**Tool contract order is load-bearing:** resolve+phase → schema validate → permit (allow/deny/ask) → harness-injects tenant scope → budget precheck → idempotency key if mutating → execute with timeout → persist >50k chars as a 2KB preview. Every rejection is an observation with remediation — never a bare `except Exception`.

**Cost reality (Atlas example):** POC estimated $0.055/call; production landed at $0.0348/call → $0.162/session → ~$39k/mo at 8k sessions/day. The gap was retrieval re-sent every turn + a 5th verify call + cache misses. Lever order: prompt cache on a frozen prefix (61% cache hit, −34% cost) > model routing (RouteLLM-style, ~48% cheaper) > fewer output tokens > fewer steps > semantic cache last (only 20–45% real hit rate).

**Eval gate (blocking on any prompt/tool/graph/model change):** deterministic checks ≥0.95 no regression, trajectory F1 ≥0.85, judge score ≥4.1 (±0.15), p95 cost ≤$0.45, a 22-case critical-safety subset at 100%. Outcome-only evals pass 20–40% *more* cases than trajectory evals — they overstate readiness.

**Deployment is deliberately unremarkable:** CPU-only pods (GPUs live behind the model gateway, not in your service), KEDA scaling on queue depth (never HPA-on-CPU), 600-second termination grace period, canary rollout scored on judge quality — not CPU/5xx, because a bad prompt still returns 200 OK.

**If you had two weeks instead of two months:** cut multi-agent, memory, compaction complexity, the permission DSL, semantic cache. Keep: Postgres checkpointer, the tool contract, budgets, traces, and the eval gate.

## 20 GenAI/Agent System Designs (RAG@10M, LLM Gateway, Agent Platform...)

**30-sec:** GenAI system design is ordinary distributed design with three additions that change every answer: the core component is probabilistic (correctness is a distribution you measure, not assert), expensive per request (~$0.01–0.30 vs ~$0.0001 for a normal API call, so cost is architecture, not a footnote), and slow (1–10s vs 50ms, so streaming/caching/step-reduction are architecture, not optimisations). Every GenAI answer needs four artefacts a conventional design doesn't: cost per request with the arithmetic shown, an eval strategy, a failure mode for silent wrongness (200 OK with a confidently incorrect answer), and a trust boundary where privileged actions are authorised by code, never by the model.

**Six slots, every design:** clarify (what the number means, read:write, latency, tenant, "correct") → architect (write path and read path drawn separately) → decide (3–5 forks: "X over Y because Z, at the cost of W") → size (QPS → bytes → tokens → $/request → $/month, unprompted) → break (failure → observable symptom → mitigation) → defend (the 3 hardest follow-ups, answered first).

**Seven recurring patterns across all 20 designs:** write path ≠ read path · two-stage retrieval is universal (cheap filter → expensive rescore, in whatever domain) · the enforcement boundary must be unbypassable (gateway+netpol, not a prompt) · version everything behaviour-changing and put it on the trace · state $/request out loud, then $/month · every failure needs an observable symptom · filter (classifier/label/prompt) vs boundary (perms/netpol/sandbox) — never conflate the two.

**Cost/routing levers everyone should know cold:** RouteLLM-style routing gets ~95% of top-model quality at ~26% strong-model calls, ~48% cheaper (production reports 40–85% in practice, plan for 40–50%). Semantic cache honest hit rate is 20–45% (30–70% for FAQ-heavy traffic); GPTCache's default threshold of 0.7 is too loose — start at 0.92 and tune down 0.01 at a time.

**Vector scale boundary:** pgvector is fine under ~5–10M vectors; past that, a dedicated engine earns its cost. 1024-dim vectors: fp16 2KB, int8 1KB, binary 128B per vector — 100M vectors ranges 200GB (fp16) down to 12.8GB (binary).

## If you remember nothing else

1. Shipping an agent is 15% agent, 85% platform — the interview lives in the 85%: durable state, budgets, permissions, evals, traces.
2. The three state boundaries (model stateless, process unreliable, trust porous) explain almost every hard production problem in one sentence each.
3. Cost drifts 3–4× between POC estimate and production reality — usually from re-sent retrieval, an extra verify call, and cache misses. Measure it, don't guess it.
4. Outcome-only evals pass 20–40% more cases than trajectory evals — they systematically overstate readiness. Trajectory eval is the honest number.
5. A bad prompt still returns 200 OK — canary rollouts must be scored on judge quality, not CPU or 5xx rate.
6. GenAI design needs four artefacts a normal design doesn't: cost/request shown as arithmetic, an eval strategy, a silent-wrongness failure mode, and a code-enforced (not prompt-enforced) trust boundary.
7. Two-stage retrieval (cheap filter, expensive rescore) is the one pattern that recurs across all 20 GenAI designs — recognize it and reuse it.
8. If you had two weeks not two months: keep the checkpointer, the tool contract, budgets, traces, and the eval gate; cut multi-agent, memory, and the permission DSL first.

## Numbers table

| Fact | Value |
|---|---|
| Agent effort split | 15% agent / 85% platform |
| POC-to-prod cost drift | 3–4× |
| Prompt caching cost reduction (frozen prefix) | −34% at 61% cache hit rate |
| Model routing savings | ~48% cheaper, ~95% top-model quality (prod: 40–85%) |
| Semantic cache honest hit rate | 20–45% (30–70% FAQ-heavy) |
| Semantic cache threshold starting point | 0.92 (not GPTCache's default 0.7) |
| Eval gate thresholds | deterministic ≥0.95, trajectory F1 ≥0.85, judge ≥4.1±0.15, p95 cost ≤$0.45 |
| Outcome-eval vs trajectory-eval overstatement | 20–40% more cases pass |
| GenAI cost per request vs normal API | $0.01–0.30 vs ~$0.0001 |
| GenAI latency vs normal API | 1–10s vs ~50ms |
| pgvector vs dedicated engine boundary | ~5–10M vectors |
| 1024-dim vector size (fp16 / int8 / binary) | 2KB / 1KB / 128B |
| Termination grace period (K8s agent pods) | 600 seconds |
