# The Latency/Accuracy/Cost Triangle: Where to Spend, What to Cut

> **Track:** T06 RAG (Retrieval-Augmented Generation) · **Time:** 2h · **Prereqs:** 01-chunking, 03-vector-index-internals, 04-hybrid-search · **Updated:** 2026-07-26
> **Module id:** `T06-latency-accuracy` · **Tags:** sprint, tradeoffs, critical

## The 30-second version

A RAG pipeline's end-to-end latency budget is spent, in order of typical magnitude, on generation first, reranking second, ANN search third, and query embedding fourth — which means the stage everyone tunes obsessively (the vector index) is usually not where the time actually goes. The standard production pattern is a cascade: cheap, wide retrieval (hybrid BM25 + dense ANN, top 50-150 candidates) optimized for recall, followed by an expensive, narrow rerank (cross-encoder, top-20 or fewer) optimized for precision — because reranking every candidate in the corpus is prohibitive, but reranking a small pre-filtered set is not. Every additional point of recall past what your reranker and generator can actually use is close to worthless: retrieving 150 candidates when only the top 5 will ever reach the LLM buys nothing extra, and stacking retrieval-quality techniques (hybrid, contextual retrieval, reranking, query reformulation) gives diminishing, sub-additive precision returns while their latency costs stay additive. The discipline that separates a senior answer from a junior one here is refusing to guess: build the budget from measured p50/p99 numbers per stage, cut the reranker only when an eval shows stage-1 recall is already sufficient for the task, and decide every one of these tradeoffs from an online metric (task success, not just recall@k), not opinion.

## Why this gets asked

The interviewer has been in the room when a PM asked for "the highest possible accuracy" with no latency budget attached, and separately been paged when a "small" accuracy improvement (one more reranking pass, a bigger top-k) quietly doubled p99 latency or tripled inference cost with no measurable improvement in what users actually experienced. They want to see you build a real number-backed budget under a stated constraint, name where the marginal dollar or millisecond is best spent, and say "no" to a change that isn't earning its cost — this is a judgment question, not a knowledge-recall question.

---

## Lineage: past → present → future

**What came before.** Early RAG systems (2022–2023) were built and evaluated almost entirely on recall@k and offline retrieval benchmarks, treating "better retrieval" as an unconditional good — more candidates, bigger embeddings, an extra rerank pass — with little attention to what it cost in latency or money at production query volume. The pain that exposed this: teams that shipped retrieval improvements measured only against offline recall found those improvements either invisible to end users (because the LLM was already ignoring the marginal candidates) or actively harmful (added latency pushed the whole interaction past a usability threshold, or added cost made the feature economically unviable at scale).

**Where it stands now.** The cascade pattern — cheap wide retrieval, then expensive narrow rerank — is the accepted production default, and Anthropic's own Contextual Retrieval evaluation makes the shape of the cascade explicit: retrieve a wide top-150, rerank down to top-20 with a cross-encoder (they used Cohere's reranker), because reranking all candidates in a large corpus is not viable but reranking 150 is. The live disagreement is *where exactly* to draw the cascade's boundaries and whether the second stage (reranking) is worth its cost at all for a given task — evidence increasingly shows that stacking multiple retrieval-quality techniques (hybrid retrieval, contextual retrieval, reranking, query reformulation) does not give additive precision gains; rerank-over-hybrid often matches rerank-over-dense-only, and layering techniques shows a precision return that flattens well before a latency cost that doesn't. A commonly cited defensible target for the retrieval-plus-rerank portion of an interactive pipeline is roughly 200-300ms, with reranking specifically tolerating a wider 100-500ms range depending on how much of the total budget is available.

**Where it's heading.** More systems are moving toward measuring and gating on downstream task success (user-facing metrics: thumbs up/down, follow-up-query rate as a proxy for failure, task completion) rather than offline recall@k alone, treating recall as a leading indicator to validate against, not the target itself — this is a real and growing practice, moderate-to-high confidence. Adaptive, query-dependent budgets (cheap path for easy queries, full cascade only when a fast confidence signal says the easy path is insufficient) are appearing in production agentic RAG systems — real but not yet universal. More speculative: learned routers that decide per-query how much retrieval and reranking budget to spend, replacing a fixed cascade with a policy — exists in research and a handful of advanced deployments, not yet a settled pattern.

---

## Mental model

Think of the 2-second end-to-end budget as a waterfall, not a pool everyone draws from equally — most of it belongs to generation before you've spent anything on retrieval:

```
0ms                                                                    2000ms
├──────┬────────────────┬──────────────────────┬────────────────────────┤
│ embed │  ANN retrieval  │       rerank         │       generation       │
│ query │  (hybrid top-k) │  (cross-encoder,     │   (LLM, streamed)      │
│50-100ms│    50-150ms     │   top-100→top-10,    │                        │
│        │                 │      150-300ms)      │    remaining ~1.2-1.5s │
├──────┴────────────────┴──────────────────────┴────────────────────────┤
   ~10% of budget            ~10-15% of budget         ~60-75% of budget
   (fixed cost, small)    (this is what people tune obsessively)   (this is where the time actually is)
```

The stage everyone spends the most engineering effort tuning — the vector index's `efSearch`/`nprobe` — is typically the smallest slice of the total budget. The reranker is the second-largest controllable slice and the one most worth deliberately cutting when it isn't earning its keep. Generation dominates and is the least directly controllable without changing the model itself or the length of what it's asked to produce.

---

## How it actually works

### Building the budget: a worked example against a 2-second target

Rough per-stage latency figures, gathered from current provider documentation and benchmarks (treat these as starting points to validate against your own measured p50/p99, not fixed truths):

| Stage | Typical latency | Notes |
|---|---|---|
| Query embedding | 50-100ms | Voyage's lightweight models report ~52ms for a single query up to 200 tokens; batching many documents at ingest time (not query time) cuts per-document latency 40-60%, but query-time embedding is inherently single-item |
| ANN retrieval (hybrid BM25 + dense) | 50-150ms | Depends heavily on corpus size and whether a metadata filter is selective (see the filtered-search problem in the vector-index-internals module) |
| Cross-encoder rerank | 100-300ms | Cohere's hosted reranker reports 100-300ms typical latency; self-hosted BGE-reranker-v2-m3 runs roughly 50ms per query-passage pair on an L40S GPU, or ~130ms per 16-pair batch on CPU |
| Prompt assembly | <10ms | Negligible, but real at very high QPS if done naively (e.g., re-serializing large contexts per request) |
| LLM generation | remaining budget | By far the largest and least controllable slice; dominated by output token count and model size, not by anything retrieval-side |

A defensible allocation against a 2-second end-to-end target:

```
embedding:        75ms   (  ~4%)
ANN retrieval:   100ms   (  ~5%)
rerank:          250ms   ( ~12%)
overhead/buffer: 75ms    (  ~4%)
generation:      1500ms  ( ~75%)  ← the dominant, least-compressible cost
─────────────────────────────
total:           2000ms
```

The immediate implication: shaving 20ms off ANN search by obsessively tuning `efSearch` is a rounding error against the budget; the two levers that actually move the total are (a) whether you rerank at all, and how many candidates you rerank, and (b) the generation stage — model choice, output length, and whether you stream the first token to hide latency from perceived UX even though total generation time is unchanged.

### Where does each extra point of recall cost you, and when does it stop being worth buying?

Retrieving more candidates (raising `top-k` at the ANN stage) costs you in three places simultaneously, and only two of them are obvious:

1. **Reranker cost and latency** — scale roughly linearly with the number of candidates reranked. Doubling `top-k` from 50 to 100 roughly doubles reranker latency and API cost (Cohere prices per search of up to 100 documents; documents over 500 tokens are split into billed sub-chunks, so long documents can push one logical search into several billed units).
2. **Context-window token cost at generation** — every candidate that survives reranking and reaches the LLM costs input tokens, and that cost is linear in the number and size of retrieved chunks passed into the prompt.
3. **The non-obvious one: quality can go down, not just cost up.** Beyond a certain number of retrieved chunks in context, models exhibit a "lost in the middle" effect — degraded attention to information buried in the middle of a long context — so blindly adding more candidates "to be safe" can measurably hurt the final answer, not just waste money.

The recall curve itself has diminishing returns baked in: Anthropic's own contextual-retrieval evaluation found passing the top-20 chunks outperformed top-10 or top-5, but that gain was measured with a matched reranking stage; there's a point past which additional recall stops changing which chunks the reranker would have surfaced anyway, because the correct answer was already inside a smaller top-k. Buying recall past that point is pure cost with no accuracy return — and the only way to know where that point is for your corpus is to measure it, not assume a fixed number generalizes.

### The cascade pattern, explicitly

```
query
  │
  ▼
Stage 1 — WIDE, CHEAP: hybrid BM25 + dense ANN over the full corpus
          optimizes for RECALL, tolerates lower precision
          top-50 to top-150 candidates
  │
  ▼
Stage 2 — NARROW, EXPENSIVE: cross-encoder rerank
          optimizes for PRECISION over the already-reduced candidate set
          top-3 to top-20 survive to the prompt
  │
  ▼
generation
```

This works because the two stages have opposite cost structures relative to corpus size: stage 1's cost is roughly independent of how many candidates you keep (an ANN index returns top-150 about as fast as top-20, since the expensive part is the graph traversal, not the final sort), while stage 2's cost scales directly with candidate count and cannot be run over the whole corpus at interactive latency. Running the expensive stage only over the cheap stage's already-narrowed output is what makes the combination affordable at all.

**Diminishing, non-additive returns when stacking techniques.** Layering hybrid retrieval, contextual retrieval, reranking, and query reformulation does not give additive precision gains — evidence from production evaluations shows rerank-over-hybrid retrieval often matches rerank-over-dense-only retrieval, meaning the hybrid leg's contribution gets partially subsumed once a reranker is in the loop, and reformulation-plus-rerank can overlap in which failures each one fixes. The practical implication: don't add a fourth technique on faith that it stacks; measure the marginal gain of each addition against your eval before keeping it, because the latency cost of adding a stage is close to guaranteed while the accuracy gain is not.

### When to cut reranking

Cut the reranker when any of these hold, verified with data rather than assumed:

- **Stage-1 recall is already sufficient for the task.** If an eval shows the correct answer is reliably in the top-3 to top-5 of the hybrid retrieval stage already, a reranker's precision gain over an already-precise set is close to zero.
- **The latency budget doesn't afford it.** Sub-500ms end-to-end targets (voice assistants, inline autocomplete-style features) often cannot absorb a 150-300ms reranking stage at all; in that regime, invest instead in a better stage-1 retriever (better embeddings, better hybrid fusion) since that's the only budget you have.
- **The corpus is small enough that top-k spread is already precise.** A few thousand well-curated documents rarely need a second precision pass; the value of reranking scales with how much noise stage-1 retrieval has to wade through.
- **Cost at your actual QPS makes an API-based reranker prohibitive.** At high query volume, self-hosting a reranker (BGE-reranker-v2-m3, run on your own GPU) changes the economics versus a hosted per-query API, and that changes when reranking is "worth it" independent of accuracy — this is a cost decision, not just a latency or accuracy one.

### Deciding with data, not opinion

The discipline that separates a defensible answer from a guess:

1. **Offline eval first** — recall@k, MRR, or nDCG against a held-out, representative query set, to gate any change before it reaches production at all. This catches regressions cheaply but does not by itself prove a change improves the user-facing outcome.
2. **Shadow or canary deployment** to measure the *actual* latency distribution under real traffic, not a synthetic benchmark — p50 and p99 diverge substantially under load, and a change that looks free in a benchmark can still blow the tail latency budget in production.
3. **Online A/B test on a downstream, user-facing metric** — task completion, explicit feedback, or a proxy like follow-up-query rate (a high rate of immediate rephrased follow-ups is a strong signal the first answer failed) — because offline recall@k can improve while the metric that actually matters (did the user get what they needed) does not move, or vice versa.
4. **Only then** commit the change, and keep the eval and the online metric both running afterward, since corpus drift or query-distribution shift can silently invalidate a decision that was correct when it was made.

---

## Build it from scratch

A minimal latency-budget calculator — useful for exactly the "build a budget live in the interview" exercise this module is about.

```python
# untested sketch — a budgeting tool, not a production system
from dataclasses import dataclass

@dataclass
class Stage:
    name: str
    latency_ms: float
    scales_with_k: bool = False  # does latency grow with candidate count?

def build_budget(total_budget_ms: float, stages: list[Stage], top_k: int = 1) -> dict:
    fixed = sum(s.latency_ms for s in stages if not s.scales_with_k)
    scaling = [s for s in stages if s.scales_with_k]
    scaling_cost = sum(s.latency_ms * top_k for s in scaling)
    used = fixed + scaling_cost
    remaining = total_budget_ms - used
    return {
        "fixed_ms": fixed,
        "scaling_ms_at_k": scaling_cost,
        "used_ms": used,
        "remaining_for_generation_ms": remaining,
        "over_budget": remaining < 0,
    }

pipeline = [
    Stage("embed_query", 75),
    Stage("ann_retrieval", 100),
    Stage("rerank_per_candidate", 2.5, scales_with_k=True),  # ~250ms at k=100
]

print(build_budget(2000, pipeline, top_k=100))
# {'fixed_ms': 175, 'scaling_ms_at_k': 250.0, 'used_ms': 425.0,
#  'remaining_for_generation_ms': 1575.0, 'over_budget': False}
```

Running this with different `top_k` values live is exactly how you'd defend a cascade width decision in an interview — show the marginal latency cost of raising `top_k` from 50 to 150 and connect it back to whether the reranker's precision at that width is actually earning its keep against an eval.

---

## How it's done in production

**Rerankers**: Cohere Rerank (hosted API, $0.001-$0.0025 per search of up to 100 documents, 100-300ms typical latency), BGE-reranker-v2-m3 (open-source, self-hostable, ~50ms/pair on an L40S GPU or ~130ms per 16-pair CPU batch), Voyage's reranker. **Embeddings**: OpenAI text-embedding-3 family, Voyage (fast single-query latency, e.g. ~52ms for short queries on the lite models), Cohere Embed — all with meaningfully different latency-vs-batch-size behavior, so benchmark against your own query shape rather than trusting a vendor's headline number. **Cascade orchestration**: typically hand-rolled in the application layer (retrieve wide, rerank narrow, assemble prompt) rather than a single off-the-shelf component, since the right cascade widths are corpus- and task-specific.

| Symptom | Cause | Fix |
|---|---|---|
| p99 latency far exceeds p50 under load | Reranker or embedding API calls made synchronously and serially instead of in parallel/batched; tail latency dominated by a slow external call | Parallelize independent stages, add timeouts with fallback (retrieve-only, skip rerank) rather than blocking |
| Adding a reranker improved offline nDCG but user satisfaction didn't move | Stage-1 recall was already sufficient for the task; the reranker's precision gain was invisible to users because the top result was already correct often enough | Measure the marginal *online* metric before keeping a change that only improves an offline proxy |
| Retrieval latency doubled after raising top-k "to be safe" | Reranker cost scales with candidate count; doubling top-k roughly doubles rerank stage latency and cost with no guaranteed accuracy gain | Sweep top-k against an eval to find the point where additional recall stops changing the reranked outcome, and stop there |
| Answer quality dropped after increasing the number of chunks passed to the LLM | Lost-in-the-middle effect — more context does not mean better attention to the right part of it | Rerank harder and pass fewer, higher-confidence chunks rather than more chunks |
| Cost per query became unsustainable at scale | Hosted reranker API billed per search, and per-query cost was never modeled against production QPS before launch | Model cost at expected QPS before choosing hosted vs. self-hosted; self-host (BGE-reranker) past the QPS where hosting is cheaper |
| A retrieval-quality improvement that passed eval made things worse in production | Offline eval query distribution didn't match real production queries, or the eval measured recall@k while the regression was in downstream generation quality | Validate with online A/B on a user-facing metric before fully rolling out, not just an offline eval pass |

---

## Tradeoffs & when NOT to use it

- **Don't rerank when stage-1 recall already meets the task's precision bar.** Reranking is a cost you pay for precision you don't always need; measure before adding it, don't add it reflexively because "reranking is best practice."
- **Don't chase maximum recall as an unconditional goal.** Every additional candidate past what the reranker/generator can actually use costs latency, tokens, and money for no accuracy return, and past a threshold can actively hurt quality via context dilution and lost-in-the-middle effects.
- **Don't stack retrieval-quality techniques without measuring each one's marginal contribution.** Hybrid retrieval, contextual retrieval, reranking, and query reformulation each cost latency additively but do not each contribute accuracy additively — verify the marginal gain of each addition against your eval before keeping it.
- **Don't optimize the smallest slice of the budget.** Tuning ANN search parameters when generation dominates 60-75% of the total latency is optimizing the wrong stage; know your own budget breakdown before deciding where to spend engineering effort.
- **Don't decide any of this from intuition when you have the means to measure it.** A senior/staff-level answer to "should we cut the reranker" is "here's what the eval and the online metric say," not "I think it's probably fine" — the whole point of this module is that these are empirical questions with empirical answers.

---

## Interview questions

### Q1 — Given a 2-second end-to-end latency target, build a budget across embedding, ANN search, reranking, and generation.
**Testing:** whether the candidate treats this as an engineering exercise with real numbers, not a vague gesture at "make it fast."
**Answer:** A defensible allocation: ~75ms query embedding, ~100ms ANN retrieval, ~250ms reranking (over roughly top-100 candidates), ~75ms overhead/buffer, leaving ~1500ms — roughly 75% of the total budget — for generation, which dominates because it's the least compressible stage without changing the model or output length.
**Follow-up trap:** *"What's the first thing you'd cut if you were 300ms over budget?"* — reranking width or the reranker entirely, not the embedding or ANN stages, because reranking is the largest controllable slice that isn't generation itself, and its marginal value is the easiest of the four to verify empirically before cutting.

### Q2 — Why does generation dominate the latency budget, and what can you actually do about it?
**Answer:** Generation latency is driven by output token count and model size/architecture, both largely outside retrieval's control. Levers that exist: choosing a smaller/faster model where quality allows, capping or guiding output length, and streaming the first token to hide total latency from perceived UX even though total generation time is unchanged.
**Follow-up trap:** *"Does streaming actually reduce latency?"* — no, it reduces *perceived* latency by showing output incrementally; total time-to-completion is unchanged, and if your success metric depends on the complete answer (not just the first visible token), streaming doesn't help that metric.

### Q3 — When would you cut reranking from a RAG pipeline?
**Answer:** When an eval shows stage-1 recall already puts the correct answer reliably in the top few candidates (a reranker's precision gain over an already-precise set is marginal); when the latency budget genuinely can't absorb 100-300ms (sub-500ms targets); when the corpus is small enough that retrieval noise is already low; or when reranking cost at your actual QPS is uneconomical and better spent improving stage-1 retrieval instead.
**Follow-up trap:** *"Isn't reranking always a net positive for quality, even if marginal?"* — usually yes in isolation, but "marginal positive, real cost" is exactly the case where cutting it is the right call; a senior answer weighs the cost against the marginal gain rather than treating any positive gain as automatically worth keeping.

### Q4 — Explain the cascade retrieval pattern and why it's structured that way.
**Answer:** Stage 1 runs cheap, wide retrieval (hybrid BM25 + dense ANN) over the full corpus optimized for recall, producing 50-150 candidates; stage 2 runs an expensive, narrow cross-encoder rerank only over that already-reduced set, optimized for precision. It's structured this way because ANN retrieval's cost is roughly independent of how many candidates you keep, while reranking's cost scales directly with candidate count and can't be run over an entire large corpus at interactive latency — you can only afford the expensive stage by first shrinking what it has to process.
**Follow-up trap:** *"What determines the width of stage 1's output?"* — an eval sweep: widen top-k until additional recall stops changing what the reranker would surface anyway, then stop — going wider past that point buys nothing but reranker cost.

### Q5 — Where does an extra point of recall stop being worth buying?
**Answer:** Once the correct answer is already reliably inside the narrower set your reranker and generator will actually use — additional recall past that point produces candidates that never influence the final answer, while still costing reranker latency/API spend and generation-time context tokens. It can also actively hurt via lost-in-the-middle effects if those extra candidates make it into the LLM's context.
**Follow-up trap:** *"How do you find that point in practice?"* — sweep retrieval `top-k` against your recall@k eval and watch where the curve flattens; that flattening point, not a fixed default, is where you stop buying recall.

### Q6 — A PM asks for "the highest possible retrieval accuracy" with no stated latency or cost budget. How do you respond?
**Testing:** whether the candidate can push back constructively rather than either refusing or silently over-engineering.
**Answer:** Ask what the actual constraint is — every accuracy gain trades against latency, cost, or both, and "highest possible" without a budget is not an engineering target. Propose a concrete tradeoff: name a latency/cost ceiling, build the budget against it (as in Q1), and show what accuracy that ceiling actually buys, then let the PM choose the point on the curve rather than assuming a number.
**Follow-up trap:** *"What if they insist on 'just make it as accurate as possible, cost be damned'?"* — even then, name that this has a ceiling too: past a certain point, more retrieved context degrades quality via lost-in-the-middle, so "unlimited accuracy spend" is not the same as "unlimited accuracy," and you should say so explicitly.

### Q7 — Why don't retrieval-quality techniques stack additively?
**Answer:** Techniques like hybrid retrieval, contextual retrieval, reranking, and query reformulation partially overlap in which failure modes they fix — evidence shows rerank-over-hybrid often matches rerank-over-dense-only, meaning the reranker's precision gain subsumes much of what the hybrid leg was contributing once both are in the pipeline. Layering techniques shows a precision return that flattens while the latency cost of each additional stage keeps accumulating linearly.
**Follow-up trap:** *"So should you never combine techniques?"* — no, combine them, but measure the marginal contribution of each addition against your eval rather than assuming stacking always helps; keep only the combinations that measurably earn their latency cost.

### Q8 — How do you decide between a hosted reranker API and self-hosting one?
**Answer:** Model cost at your actual expected QPS: a hosted API (e.g., Cohere Rerank at roughly $0.001-0.0025 per search of up to 100 documents) is simpler operationally but its per-query cost is linear in query volume; self-hosting an open model (BGE-reranker-v2-m3, ~50ms/pair on an L40S GPU) has fixed infrastructure cost that becomes cheaper per-query past some QPS threshold. The crossover point is a real number you should compute for your own volume, not assume.
**Follow-up trap:** *"What about latency, not just cost?"* — self-hosting typically gives more predictable p99 latency (no external network hop, no third-party rate limiting), which can matter as much as raw cost once you're operating at meaningful scale.

### Q9 — How do you decide a retrieval-pipeline change is actually an improvement, rather than just trusting the eval?
**Answer:** Gate with an offline eval first (recall@k, nDCG against held-out queries) to catch regressions cheaply, then validate the change online — shadow/canary for real latency distribution, then an A/B test against a downstream user-facing metric (task success, explicit feedback, or a proxy like follow-up-query rate). Offline recall@k improving does not guarantee the online metric moves, and shipping on offline eval alone is exactly how "improvements" that don't help users get shipped.
**Follow-up trap:** *"What if the online test takes weeks to reach significance and the team wants to move faster?"* — say plainly that shipping without online validation is a real, named risk being accepted, not a non-issue; a senior engineer surfaces that tradeoff explicitly rather than skipping the step silently.

### Q10 — Trap: a teammate proposes "just retrieve more chunks and pass them all to the LLM — more context can only help." What's wrong with this?
**Answer:** More retrieved chunks cost more reranker latency (if reranked) or dilute reranking benefit (if not), cost more input tokens at generation, and past a threshold measurably hurt answer quality via lost-in-the-middle effects — attention degrades on information buried in the middle of a long context. "More context can only help" is false past the point where the correct information is already reliably present; beyond that it's pure cost, and sometimes net-negative for quality.
**Follow-up trap:** *"How would you convince them with data rather than argument?"* — run the eval at increasing top-k/context sizes and show where the accuracy curve flattens or reverses; a concrete curve settles the argument better than restating the mechanism.

### Q11 — What's the actual latency cost difference between a self-hosted BGE reranker and a hosted API reranker, and when does that difference matter?
**Answer:** Self-hosted BGE-reranker-v2-m3 on a GPU (e.g., L40S) runs roughly 50ms per query-passage pair, competitive with or faster than hosted APIs reporting 100-300ms typical latency, but the hosted API includes network round-trip and third-party queuing that a self-hosted deployment avoids. This matters most when you're near the edge of a tight latency budget (sub-500ms end-to-end) where every external network hop is a meaningful fraction of the total.
**Follow-up trap:** *"Does self-hosting always win on latency, then?"* — not necessarily at low QPS, where the hosted API's operational simplicity may outweigh a latency difference that doesn't matter against your actual budget; the decision should be budget-driven, not a blanket preference.

### Q12 — Staff-level: your retrieval pipeline meets its 2-second latency target and passes offline eval, but online task-completion rate hasn't improved after shipping three successive "retrieval quality" improvements. What do you do?
**Testing:** the judgment this whole module is built around.
**Answer:** Stop shipping further retrieval-side changes on the assumption they'll help, and instead instrument where the pipeline is actually failing — pull a sample of failed interactions and check whether the failure is upstream (retrieval genuinely missing the right content), midstream (retrieved correctly but reranked poorly), or downstream (retrieved and ranked correctly but the LLM failed to use the context, e.g., a lost-in-the-middle effect from too much context, or a generation-quality issue unrelated to retrieval at all). Given that three successive retrieval improvements didn't move the online metric while presumably improving or holding offline eval steady, the strongest hypothesis is that the bottleneck has moved downstream of retrieval — worth checking generation quality, prompt structure, and context size before assuming a fourth retrieval change will help.
**Follow-up trap:** *"Wouldn't reverting the three changes be the safe move?"* — only if you have evidence they're net-negative, not just non-positive; reverting on that basis alone throws away real recall/precision gains for no proven reason. Diagnose the actual bottleneck first, then decide what to keep, cut, or revert based on that.

---

## Red flags that fail you

- Naming a latency target with no per-stage breakdown behind it.
- Assuming more retrieved candidates or a bigger top-k is unconditionally better.
- Treating recall@k improvements as automatically meaningful without checking the downstream user-facing metric.
- Not knowing generation typically dominates the latency budget, not retrieval.
- Recommending reranking reflexively without checking whether stage-1 recall already suffices.
- Assuming retrieval-quality techniques stack additively in accuracy while ignoring that their latency costs do stack additively.
- Deciding a tradeoff "because it feels right" when an eval or online test was available and wasn't run.

---

## Cheat card

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

## Sources

- [Introducing Contextual Retrieval — Anthropic](https://www.anthropic.com/engineering/contextual-retrieval) — accessed 2026-07-26
- [Cohere Rerank pricing and latency — Cohere API Pricing 2026](https://www.aipricing.guru/cohere-pricing/) — accessed 2026-07-26
- [Best Rerankers for RAG in 2026: 7 Models Compared — FutureAGI](https://futureagi.com/blog/best-rerankers-for-rag-2026/) — accessed 2026-07-26
- [Top 8 Rerankers: Quality vs Cost — Medium](https://medium.com/@bhagyarana80/top-8-rerankers-quality-vs-cost-4e9e63b73de8) — accessed 2026-07-26
- [Retrieval Latency Optimization for Production RAG Systems — Unstructured](https://unstructured.io/insights/retrieval-latency-optimization-for-production-rag-systems) — accessed 2026-07-26
- [AGENTPERF03-BP03 Optimize RAG retrieval pipelines for latency and precision — AWS Well-Architected Agentic AI Lens](https://docs.aws.amazon.com/wellarchitected/latest/agentic-ai-lens/agentperf03-bp03.html) — accessed 2026-07-26
- [Embedding API Latency Is a Retrieval Bottleneck, Not a Footnote — Medium](https://medium.com/@alexchen3292/embedding-api-latency-is-a-retrieval-bottleneck-not-a-footnote-8acfa30140c1) — accessed 2026-07-26

## Changelog
- 2026-07-26 — created
