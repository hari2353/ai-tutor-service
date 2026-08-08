# Prompt Caching, Model Routing, Fallback Chains, Cost Governance

> **Track:** T07 Agentic AI · **Time:** 1.5h · **Prereqs:** none · **Updated:** 2026-08-01
> **Module id:** `T07-agent-cost-routing` · **Tags:** production,cost

## The 30-second version

Prompt caching cuts cost by serving a repeated prefix at roughly 10% of its normal input price, as long as the prefix is byte-identical and volatile content sits after it, not inside it — so the entire discipline is "put the stable stuff first, the changing stuff last." Model routing sends easy requests to a cheap model and hard ones to an expensive one, and the boundary between "easy" and "hard" should come from a labeled eval set, not intuition, because intuition about difficulty is exactly the thing routers exist to replace. Fallback chains catch rate limits, outages, and refusals by retrying on a different model, and they cost latency every time they fire, so they're an availability tool, not a cost-optimization tool. Cost governance is the unglamorous plumbing — per-tenant budgets, quotas, and spend attributed to a feature — that turns "the bill went up" into "feature X's retry loop went up," which is the only actionable form of that sentence. And the single most reliable cost lever across all of this is not swapping to a cheaper model; it's putting fewer tokens in the context window in the first place, because every other optimization operates on the size of the bill you already have.

## Why this gets asked

Because at scale, LLM spend becomes a line item someone outside engineering asks about by name, and the interviewer has usually been the person explaining a cost spike after the fact. They want to know you understand the mechanics well enough to predict the bill before it arrives — that a cache miss on a 6,000-token system prompt at high request volume is a specific, calculable dollar amount, not a vague "caching helps." They're also probing for the honest instinct: does the candidate reach for a cheaper model first, or for fewer tokens first, because the two produce very different savings and very different risk profiles.

---

## Lineage: past → present → future

**What came before.** Early LLM applications paid full price for every token of every request, including re-sending an identical multi-thousand-token system prompt and tool schema list on every single call in a conversation — because the API was, and still is, fundamentally stateless. The pain was straightforward: a RAG application sending the same 8K-token retrieved-context block on every follow-up question in a session paid for those 8K tokens again and again, and a company running thousands of such sessions a day watched input-token cost dominate the bill even though the actual novel content per request was a single sentence. The first mitigations were manual and crude: truncating context aggressively, or maintaining a cache of full responses keyed by exact prompt match, which only helped for genuinely repeated queries and did nothing for the common case of a shared prefix with a varying suffix.

**Where it stands now.** Prompt caching at the API level (Anthropic shipped it first among the major labs, OpenAI followed with automatic caching) is now the standard first lever, because it requires no architecture change — just ordering discipline in how you build the prompt. The current consensus on model routing is that a learned or eval-driven router (in the RouteLLM lineage, trained on preference data to predict which queries a weaker model can handle as well as a stronger one) meaningfully outperforms a hand-written heuristic, but most production systems still ship simpler rule-based routing (route by task type, or by an explicit user-selected tier) because a learned router is itself infrastructure to build and maintain. The live disagreement is over the value of aggressive multi-provider fallback: some teams route fallback purely for availability (never for cost), while others treat "try the cheap model, escalate to the expensive one on low confidence" as a legitimate cost-routing strategy in its own right, blurring the line this module draws between routing and fallback.

**Where it's heading.** Two directions with different confidence. **Caching semantics keep tightening in the providers' favor and the applications'** — minimum cacheable prefix lengths are dropping (down to 512 tokens on the newest Anthropic models from 1024 previously) and the discount on cache reads has converged toward 90% across major providers, which is high-confidence because it's already shipped and observable. **Cost-aware routing as a first-class request parameter is speculative but plausible** — the direction of travel is toward providers exposing routing-by-difficulty or routing-by-budget as an API primitive rather than something every application team builds itself, but as of this writing that remains something you build, not something you call.

---

## Mental model

```
                     ┌─────────────────────────────────────────────┐
                     │              ONE REQUEST                     │
                     │  ┌───────────┐ ┌────────┐ ┌────────────────┐│
                     │  │  STABLE   │ │STABLE  │ │    VOLATILE     ││
  render order  ────▶│  │  TOOLS    │▶│SYSTEM  │▶│    MESSAGES     ││
                     │  │ (position │ │PROMPT  │ │ (varies per     ││
                     │  │    0)     │ │        │ │  request)       ││
                     │  └───────────┘ └────┬───┘ └────────────────┘│
                     │                     │                        │
                     │              cache_control HERE               │
                     │           (last byte before volatility)       │
                     └─────────────────────────────────────────────┘
                                       │
                         ┌─────────────┴─────────────┐
                         ▼                             ▼
                   CACHE HIT (~0.1x)            CACHE MISS (~1.25-2x write)
                   read the stable prefix        write it fresh, pay the premium
                   pay full price only for       once, then every subsequent hit
                   the volatile tail             within the TTL is ~0.1x
```

```
                        ┌──────────────────────────┐
   incoming request ───▶│   ROUTER (classifier or   │
                        │   rule, trained/tuned      │
                        │   against a labeled set)   │
                        └────────────┬───────────────┘
                          easy       │        hard
                     ┌────────────────┴────────────────┐
                     ▼                                   ▼
              CHEAP MODEL                          EXPENSIVE MODEL
           (Haiku-tier: fast,                  (Opus-tier: slow, dear,
            cheap, good enough                  reserved for what the
            for most traffic)                   cheap model can't do)
                     │                                   │
                     └──────────────┬────────────────────┘
                                    ▼
                          FALLBACK CHAIN (orthogonal axis)
                    fires on 429 / 5xx / refusal, NOT on "seemed hard" —
                    an availability mechanism, priced in added latency
```

The one thing to internalize: **caching, routing, and fallback are three independent levers that compose, and confusing them produces the wrong fix.** A cache-miss problem looks like "cost is high" and is solved by prompt-ordering discipline. A routing problem looks like "cost is high because everything hits the expensive model" and is solved by a difficulty boundary. A fallback problem looks like "latency spikes under load" and is solved by availability engineering, not cost engineering — using it to save money is a legitimate but different design decision.

---

## How it actually works

### Prompt caching: the mechanics and the real numbers

Caching is a prefix match. The API renders `tools` → `system` → `messages`, and any byte difference at position N invalidates the cache for everything from N onward — one stray timestamp interpolated into a system prompt, one non-deterministically-ordered JSON object, one reordered tool in the list, and the entire downstream prefix misses.

**Current economics (Anthropic, verified 2026):** a cache write costs 1.25× the standard input rate at the default 5-minute TTL, or 2× at the optional 1-hour TTL. A cache read costs roughly 0.1× the standard input rate — a 90% discount. Break-even arithmetic: at the 5-minute TTL, `1.25× + 0.1× = 1.35×` versus `2× uncached` for two requests, so you're ahead after a single cache hit. At the 1-hour TTL, `2× + 0.2× = 2.2×` versus `3× uncached` for three requests — the longer TTL needs more hits to amortize its higher write cost, but survives longer gaps in bursty traffic. OpenAI's automatic caching applies with zero code changes above a 1,024-token prefix and has converged to the same roughly 90% discount on current-generation models (older models like GPT-4o remained at a 50% discount).

**Minimum cacheable prefix is not monotonic across model generations** — 512 tokens on Claude's newest models, 1,024 on the prior generation, up to 4,096 on some older ones. A prompt sized for one model's minimum can silently fail to cache on another with no error, just `cache_creation_input_tokens: 0` in the usage response — this is the single most common "why isn't my cache working" bug, and the fix is always to check the usage fields, not to assume the marker is broken.

**What invalidates a cache, concretely:**

| Invalidator | Why |
|---|---|
| `datetime.now()` or a request UUID inside the system prompt | The prefix differs on literally every request |
| `json.dumps(d)` without sorted keys, or iterating a `set` | Non-deterministic serialization changes the rendered bytes even when the logical content is identical |
| Per-user content injected into the system prompt | Prefix becomes per-user; no cross-user sharing |
| Tools added, removed, or reordered mid-conversation | Tools render at position 0 — any change there invalidates everything downstream, including the system prompt and all prior messages |
| Switching models mid-conversation | Caches are model-scoped; there is no cross-model cache |

**The rule this all reduces to: stable content first, volatile content last, and if you must inject something dynamic, inject it as far down the render order as the API allows** — a mid-conversation system-role message appended to `messages[]` (supported on current-generation Anthropic models with no beta header) is the standard escape hatch for injecting an operator instruction without invalidating the entire cached history, precisely because it sits after the cached prefix rather than editing it.

### Model routing: setting the boundary empirically

The naive approach — "route based on prompt length" or "route based on keyword" — fails because difficulty and length are only loosely correlated, and a heuristic tuned by eye systematically misjudges the cases that matter (a short prompt asking for a subtle logical deduction, a long prompt that's mostly boilerplate). The RouteLLM line of work (UC Berkeley, ICLR 2025) demonstrates the alternative: train a lightweight classifier on preference data — which model won a head-to-head comparison on a given query — and route below a learned threshold to the cheap model, above it to the strong one. Their published results: over 85% cost reduction on MT-Bench while retaining 95% of the stronger model's judged quality, sending only 14% of queries to the expensive model in their best-tuned configuration.

**The generalizable process, independent of whether you use their specific tooling:**

1. Collect a representative sample of real production queries (not synthetic ones — router quality depends on the traffic distribution it will actually see).
2. Get quality judgments for both the cheap and expensive model on that sample — an LLM-as-judge pipeline or human labels.
3. Fit a classifier (or, as a cheaper starting point, a simple rule set) that predicts "will the cheap model match the expensive one on this query," and find the operating threshold that hits your target quality bar.
4. Route live traffic by that threshold, and **re-run the calibration whenever you change either model** — a router tuned against Haiku-vs-Opus-4.6 does not transfer to Haiku-vs-Opus-5 without re-fitting, because the quality gap the threshold was calibrated against has moved.

```python
# untested sketch — the generalizable shape, not a specific library
def route(query: str, classifier, threshold: float) -> str:
    difficulty_score = classifier.predict(query)  # trained on labeled win/loss data
    return "expensive_model" if difficulty_score > threshold else "cheap_model"
```

**Reported real-world ranges** across teams that implement a tuned routing layer run 40-85% bill reduction depending on traffic mix and how far apart the two tiers are priced — the wide range is exactly why "empirical, on your own traffic" beats citing someone else's number.

### Fallback chains: availability, not savings

A fallback chain retries a failed request on a different model or provider when the primary target returns a rate limit (429), a server error (5xx), or — for models with safety classifiers — a policy refusal. Every fallback firing costs the latency of the failed attempt plus the latency of the successful one; a chain of three fallback targets in the worst case pays for three sequential round trips before succeeding. This is why fallback belongs in the availability column, not the cost column: it exists to keep the system serving requests through an outage or a refusal, and using it as a routing-for-cost mechanism ("try cheap first, escalate on any hiccup") conflates a resilience pattern with a cost pattern and inherits the latency cost of the former to get the savings of the latter.

**Concretely, a well-formed fallback chain distinguishes:**

- **Retryable on the same model** — a transient 5xx or a 429 with a `retry-after` header — handled by backoff-and-retry, not a model switch.
- **Fallback to a different model** — the primary model is unavailable, overloaded, or (for the newest models with elevated safety classifiers) declined the request — handled by re-issuing on a named substitute, ideally one whose acceptance criteria differ enough that a benign false-positive refusal on the primary is likely to succeed on the fallback.
- **Sticky routing after a fallback fires** — once a conversation has fallen back, keeping subsequent turns on the fallback model for a bounded window avoids repeatedly re-triggering the same refusal or overload on every turn, at the cost of running the rest of the conversation on the (usually pricier, more capable) fallback tier.

### Batching: the third lever, orthogonal to caching

The Message Batches pattern processes requests asynchronously — submit up to tens of thousands of requests, poll or wait up to 24 hours, retrieve results — at a flat 50% discount on both input and output tokens, on every model, with no schema changes to the request itself. It composes multiplicatively with caching: a batch job over a shared, cached corpus (documents processed with the same system prompt and tool schema) can combine the 50% batch discount with the roughly 90% cache-read discount to land near 5% of the naive uncached, unbatched rate card for the cached portion of the request. The constraint that makes batching a distinct lever rather than a strict upgrade: it trades latency (up to 24 hours) for cost, so it only fits workloads that are not latency-sensitive — offline evaluation runs, bulk classification, nightly report generation — never an interactive user-facing request.

### Cost governance: turning "the bill went up" into an answer

None of the above matters operationally if you cannot attribute spend to its source. The concrete pieces:

- **Per-tenant or per-feature budgets**, enforced the same way a per-run cost budget is enforced in a single agent loop (see `T07-production-agent-loops`): a shared, atomically-updated ledger, not a client-side estimate, because the enforcement point has to survive horizontal scaling and retries.
- **Quotas** as a distinct control from budgets — a budget caps dollars; a quota caps request or token *volume* independent of price, which matters when the actual risk is a runaway loop rather than an expensive model choice.
- **Alerting on rate of spend, not just cumulative spend** — a tenant whose daily spend is within budget but has doubled week-over-week is a leading indicator a cumulative-only dashboard will miss until the budget is already blown.
- **Attribution requires tagging spend at the request level** with a feature or workflow identifier at the point the request is made, not reconstructed after the fact from logs — because reconstruction after the fact is exactly the exercise that fails when someone asks "which feature caused the spike" during an actual incident.

**The honest observation, and the one senior candidates are expected to volunteer without being asked:** the single highest-leverage cost lever is usually reducing the number of tokens that enter the context window in the first place — truncating tool results at the source, compacting stale history, not re-sending irrelevant retrieved documents — not switching to a cheaper model. A worked comparison from `T07-context-engineering`: truncating a chatty tool result from 4K tokens per turn down to 1K, across a 40-turn run with a 6K stable prefix, drops total tokens from roughly 1.16M to about 0.30M — a bigger reduction than most single-tier model downgrades produce, and it stacks with caching and routing rather than substituting for either.

---

## Build it from scratch

There is no dedicated lab for this module; it composes three independently testable pieces you can build and verify separately: (1) a prompt-builder function that enforces render order and asserts the stable prefix is byte-identical across calls (verify via `response.usage.cache_read_input_tokens` on the second identical call — nonzero means it worked), (2) a routing function taking a labeled query set and a threshold, scored against a held-out set for the quality/cost tradeoff curve, and (3) a budget ledger with a reservation-and-credit API, load-tested with concurrent callers to confirm it doesn't overshoot under race conditions — the same test that would catch the client-only-budget bug in `T07-production-agent-loops`.

---

## How it's done in production

**Tooling map:** prompt caching is a request-shape concern handled directly against the provider API — no framework required, just discipline in prompt construction. Model routing has both DIY (RouteLLM as an open-source starting point) and managed options (several LLM gateway products expose routing as a config-driven feature). Fallback chains are increasingly a first-class API parameter on some providers (server-side fallback configuration that retries on a named substitute model within the same call, rather than requiring client-side retry logic) rather than something every team hand-rolls. Batch processing is a provider API endpoint, not a framework choice.

**What breaks at scale**

| Symptom | Cause | Fix |
|---|---|---|
| `cache_read_input_tokens` is zero across repeated identical-looking requests | A silent invalidator: unsorted JSON serialization, a timestamp in the system prompt, or a varying tool set | Diff the rendered prompt bytes between two requests; fix the non-determinism at the source |
| A 3K-token prompt caches on one model and silently doesn't on another | Minimum cacheable prefix differs by model generation (512 to 4,096 tokens) and there's no error, just a zero-token cache-creation field | Check the model-specific minimum before assuming a marker placement bug |
| Router quality degrades after a model upgrade with no code change | The router's difficulty threshold was calibrated against the old model pair's quality gap, which has now shifted | Re-run the calibration process against the new model pair; don't assume a stale threshold transfers |
| Fallback chain adds noticeable p99 latency under normal (non-outage) load | Fallback is firing on transient conditions that should have been a same-model retry, not a model switch | Separate retryable-same-model conditions (5xx, 429 with backoff) from genuine-unavailability conditions before escalating to a different model |
| "The bill went up" with no actionable next step | Spend was never tagged by feature/tenant at request time | Tag every request with a feature/workflow identifier at the point of the call, not reconstructed later from logs |
| Batch job costs more than expected despite the 50% discount | The corpus wasn't also cached — batch and cache discounts are independent and both need to be deliberately combined | Structure the batch requests to share a cached system prompt/context block, not just submit them as a batch |
| A cheaper model swap didn't move the bill much | Token volume, not model price, was the dominant cost driver | Measure tokens-per-request before assuming the model tier is the lever; truncation/compaction often outperforms a model downgrade |

---

## Tradeoffs & when NOT to use this

- **Don't cache a prompt whose prefix differs from the start on every request.** If the first thousand tokens are unique per call, there is no reusable prefix, and adding a `cache_control` marker only pays the write premium with zero subsequent reads — leave it off rather than caching reflexively.
- **Don't route on cost alone if the quality bar for the wrong answer is asymmetric.** A cheap-model misroute on a customer-facing financial calculation is not the same risk as a misroute on a casual chat reply; the routing threshold should be set against the actual cost of being wrong on that traffic segment, not a single global quality target.
- **Don't use fallback chains as your primary cost lever.** They exist for availability and every firing costs latency; if you're routing to a cheap model first and escalating "on suspicion," that's a routing decision wearing a fallback chain's clothing, and it should be evaluated with the same empirical rigor as any router, not treated as a free cost win.
- **Don't batch anything latency-sensitive.** The 50% discount is real but comes with up to a 24-hour turnaround; an interactive user-facing feature has no business in the batch queue regardless of how attractive the discount looks on paper.
- **Don't reach for a learned router before checking whether a rule-based one is good enough.** Building and maintaining a classifier is real ongoing infrastructure — a simple rule ("route by task type," "route by an explicit user-selected quality tier") is often 80% of the savings for a fraction of the engineering, and is the right starting point before investing in a learned classifier.

---

## Interview questions

### Q1 — Explain prompt caching economics with real numbers.
**Testing:** whether the candidate has actually looked at the pricing, not just heard "caching saves money."
**Answer:** A cache write costs 1.25× standard input price at the default 5-minute TTL, 2× at the 1-hour TTL. A cache read costs roughly 0.1× — a 90% discount. At the 5-minute TTL you break even after a single hit (1.25+0.1=1.35 versus 2× for two uncached requests); at the 1-hour TTL you need three hits to break even (2+0.2=2.2 versus 3×). The discount only applies to a byte-identical prefix — any difference anywhere in it invalidates everything downstream of that byte.
**Follow-up trap:** *"Your cache read tokens are zero across ten identical-looking requests. Where do you look first?"* — a silent invalidator: `datetime.now()` or a UUID in the system prompt, non-deterministic JSON key ordering, or a tool list that reorders between calls. Diff the actual rendered prompt bytes between two requests rather than guessing from the code.

### Q2 — Why does caching require putting volatile content last, and what breaks if you don't?
**Answer:** The cache key is a prefix hash — the API renders tools, then system, then messages, and a breakpoint caches everything up to it. Any byte difference at position N invalidates the cache for every byte after N. If a timestamp or per-request ID sits early in the system prompt, the entire downstream conversation history is uncacheable regardless of how stable the rest of it is, because the invalidation propagates forward from the first point of difference.
**Follow-up trap:** *"You need to inject a mode switch mid-conversation. How do you do it without breaking the cache?"* — append it as a message after the cached prefix rather than editing the system prompt in place; on models that support it, a mid-conversation system-role message carries operator authority without touching the bytes that came before it, so the existing cached history stays valid.

### Q3 — How do you decide the routing boundary between a cheap and an expensive model?
**Answer:** Empirically, against a labeled sample of real production traffic, not intuition. Collect representative queries, get quality judgments for both models on that sample (LLM-as-judge or human labels), fit a classifier or threshold that predicts whether the cheap model matches the expensive one, and pick the operating point that hits your target quality bar. RouteLLM's published numbers (over 85% cost reduction on MT-Bench at 95% retained quality) came from exactly this process trained on real preference data, not a hand-tuned heuristic.
**Follow-up trap:** *"You upgraded the expensive model and didn't retune the router. What happens?"* — the router's threshold was calibrated against the old quality gap between the two models, and an upgraded model widens or narrows that gap. The threshold doesn't transfer automatically; you have to re-run the calibration, or you'll either overspend (routing too much to the now-unnecessarily-strong upgraded model) or underspend on quality (routing traffic that now needs the upgraded model to the cheap one).

### Q4 — What's the difference between a fallback chain and cost-based model routing, and why do people conflate them?
**Testing:** the senior distinction this whole module is built around.
**Answer:** Routing decides where a request *should* go based on predicted difficulty, evaluated empirically ahead of time. Fallback decides where a request goes *after* something went wrong — a rate limit, an outage, a safety refusal — and it's reactive, not predictive. People conflate them because "try the cheap model and escalate on low confidence" looks like fallback syntax but is functionally a router with a bad calibration method (confidence-at-generation-time instead of a pre-validated difficulty boundary), and it inherits fallback's latency cost (two sequential round trips) to buy routing's savings, which is a worse tradeoff than doing either cleanly.
**Follow-up trap:** *"So is 'try cheap, escalate on failure' always wrong?"* — no, but it should be evaluated with the same rigor as a router (measured on a labeled set, not assumed), and its latency cost should be accounted for explicitly rather than treated as free. If the escalation rate is low and latency isn't user-visible, it can be a reasonable middle ground; the trap is calling it "fallback" and exempting it from cost/quality measurement because fallback code is usually justified purely on availability grounds.

### Q5 — When is Batch API the right tool, and what's the actual combined discount with caching?
**Answer:** For non-latency-sensitive, high-volume workloads — offline evals, bulk classification, nightly reports — where you can tolerate up to a 24-hour turnaround for a flat 50% discount on both input and output tokens. Combined with prompt caching on a shared corpus, the discounts multiply rather than one subsuming the other: batch's 50% off plus caching's roughly 90% off the cached portion can land the cached-and-batched fraction of the work near 5% of the naive rate.
**Follow-up trap:** *"Your batch job's actual cost barely moved despite the 50% discount. Why?"* — the batch discount alone doesn't capture the caching discount; if the requests in the batch don't share a cached system prompt or context block, you're only getting the batch discount and none of the caching one. Structure the batch so the shared, stable portion is explicitly marked for caching, not just submitted as a flat batch of independent requests.

### Q6 — A tenant's cost dashboard shows they're within budget, but you got paged anyway. What might the dashboard be missing?
**Answer:** Rate of spend, not just cumulative spend against the cap. A tenant whose daily spend has doubled week-over-week but hasn't yet crossed the absolute budget line looks fine on a cumulative-only view and is exactly the leading indicator a rate-based alert would have caught earlier. Cumulative dashboards tell you about the past; rate-of-change alerts tell you about the trajectory.
**Follow-up trap:** *"Your budget enforcement is per-tenant but a single feature is causing the spike across many tenants. How do you find that?"* — this is why attribution has to be tagged at the request level by feature/workflow identifier, not just by tenant. Without that tag captured at call time, you're reconstructing "which feature" from logs after the fact during an incident, which is slow and error-prone exactly when you need speed.

### Q7 — Why is "swap to a cheaper model" often not the highest-leverage cost fix?
**Testing:** the honest-observation senior signal for this whole topic.
**Answer:** Because token volume, not per-token price, is frequently the dominant driver of cost, and a model swap doesn't touch volume at all. Truncating tool results at the source, compacting stale conversation history, and not re-sending irrelevant retrieved context routinely produce a bigger reduction than moving down a pricing tier — a worked example: truncating a 4K-token chatty tool result to 1K per turn across a 40-turn run drops total tokens from roughly 1.16M to about 0.30M, larger than most single-tier downgrades, and it composes with caching and routing rather than competing with them.
**Follow-up trap:** *"So should you always fix tokens before touching the model?"* — check both, but token reduction is usually higher-leverage per unit of engineering effort and it's compounding: fewer tokens in context also makes caching cheaper to write and routing easier to reason about, since a router calibrated against a bloated context is calibrated against a moving target.

### Q8 — Design a cost governance system for a multi-tenant agent platform.
**Answer:** Per-tenant budgets enforced through a shared, atomically-updated ledger (not client-side estimates, for the same TOCTOU reasons covered for per-run budgets in `T07-production-agent-loops`), with a reservation pattern to avoid overshoot under concurrent requests from the same tenant. Separately, per-tenant or per-feature quotas on raw request/token volume, independent of price, to catch runaway loops that a dollar budget alone might not flag in time. Every request tagged at call time with tenant and feature identifiers so spend is attributable without log reconstruction. Alerting on both cumulative spend against budget and rate-of-change week-over-week, because the two catch different failure shapes.
**Follow-up trap:** *"A tenant is deliberately gaming your quota by spreading a runaway loop across many small requests, each individually under any per-request limit."* — a per-request cap doesn't catch aggregate abuse; you need a windowed rate limit (requests or tokens per unit time, not just per request) and ideally anomaly detection on request pattern (a sudden 50x increase in request rate from one tenant, even if each request is small, is the signal), not just a static ceiling.

### Q9 — Your team wants to build a learned router like RouteLLM's. What would you check before investing in it?
**Answer:** Whether a rule-based router already captures most of the achievable savings for less engineering cost — routing by explicit task type, or by a user-selected quality tier, is often 80% of the win. A learned classifier needs labeled preference data on your actual traffic (not someone else's benchmark), ongoing recalibration whenever either model changes, and a mechanism to detect when the router itself has drifted from the traffic it was trained on. If none of that infrastructure exists yet, the marginal gain from a learned router over a decent rule-based one may not justify building and maintaining it.
**Follow-up trap:** *"Your rule-based router is 'route financial-calculation intents to the expensive model, everything else to the cheap one.' Where does this break?"* — intent classification itself has error, and the failure mode is asymmetric: misrouting a genuinely simple query to the expensive model is just wasted money, but misrouting a subtly complex query to the cheap model produces a wrong answer a user acts on. A rule-based router needs the same empirical validation against labeled quality outcomes that a learned one does — "rule-based" describes the mechanism, not an exemption from measurement.

### Q10 — What's the observable symptom that a fallback chain is being mis-used as a cost-saving router?
**Answer:** Noticeable p99 latency under *normal* load, not just during outages — because every fallback firing costs the latency of a failed attempt plus a successful one, and if the "primary" tier is deliberately the cheap model with the intent of escalating often, you're paying that double round-trip cost on a meaningful fraction of everyday traffic rather than only during genuine unavailability.
**Follow-up trap:** *"Isn't that just... routing with extra steps? Why does the distinction matter operationally?"* — because the two need different observability. A fallback chain's health metric is escalation rate during outages (should be near zero in steady state); a router's health metric is the quality/cost tradeoff on its threshold (should be stable and periodically re-validated). Mislabeling a router as a fallback chain means nobody is watching the metric that actually matters for it — the quality curve — because everyone's dashboards are set up to alert on outages, not on drift.

---

## Red flags that fail you

- Reciting "caching saves money" with no actual break-even numbers.
- Not knowing that caching invalidates on any byte change to the prefix, not just "big" changes.
- Routing decisions justified by intuition ("this looks like a hard query") with no labeled evaluation behind the threshold.
- Treating a fallback chain as a cost optimization with no acknowledgment of its latency cost.
- Reaching for a model downgrade before checking whether token volume is the actual driver.
- No plan for attributing spend to a feature or tenant before an incident forces you to reconstruct it from logs.
- Batching a latency-sensitive, user-facing request path.
- Assuming a router's threshold survives a model upgrade with no recalibration.

---

## Cheat card

```
PROMPT CACHING
  render order: tools -> system -> messages; breakpoint invalidates FORWARD from
    the first differing byte
  economics: write 1.25x (5min TTL) / 2x (1h TTL); read ~0.1x (90% off)
  break-even: 5min TTL after 1 hit (1.35x vs 2x); 1h TTL after 3 hits (2.2x vs 3x)
  min cacheable prefix NOT monotonic across models: 512 / 1024 / 2048 / 4096 tok
    -- silent failure below minimum, check usage.cache_read_input_tokens
  invalidators: timestamp/UUID in system prompt, unsorted JSON, reordered tools,
    model switch (caches are model-scoped, no cross-model reuse)
  escape hatch: append operator instructions as a message AFTER the cached
    prefix, don't edit system prompt in place

MODEL ROUTING
  set the boundary EMPIRICALLY: labeled query set -> quality judgments for both
    models -> fit threshold -> validate on held-out set
  RouteLLM (ICLR 2025): >85% cost cut on MT-Bench, 95% retained quality,
    14% of queries to the strong model
  reported real-world range: 40-85% bill reduction, traffic-mix dependent
  MUST recalibrate on every model swap -- threshold is gap-specific, not absolute

FALLBACK CHAINS
  AVAILABILITY tool, not a cost tool -- every firing = 2+ sequential round trips
  same-model retryable (5xx, 429+retry-after) != different-model fallback
    (outage, overload, refusal)
  "try cheap, escalate on suspicion" = a router wearing fallback's clothing;
    measure it like a router, budget its latency like a fallback

BATCH API
  50% off input+output, up to 24h turnaround, ALL models
  composes with caching (independent discounts): cached+batched -> ~5% of
    naive rate card for that portion
  NEVER for latency-sensitive / interactive paths

COST GOVERNANCE
  per-tenant/feature budget: shared atomic ledger + reservation (not client
    estimate) -- same TOCTOU risk as single-run budgets
  quota (volume) is a DIFFERENT control from budget (dollars) -- catches
    runaway loops a dollar cap alone might miss
  alert on RATE of spend, not just cumulative -- catches the trend before
    the cap is blown
  attribute by tagging at REQUEST time, not reconstructing from logs later

THE HONEST TAKEAWAY: fewer tokens in context usually beats a cheaper model.
  worked example: 4K->1K tool-result truncation over 40 turns: ~1.16M -> ~0.30M
    total tokens -- bigger than most single-tier model downgrades, and it
    stacks with caching and routing rather than competing with them
```

## Sources

- [Anthropic Prompt Caching — pricing and TTL structure](https://platform.claude.com/docs/en/build-with-claude/prompt-caching) — accessed 2026-08-01
- [Prompt Caching in 2026: Anthropic, OpenAI, Azure Compared](https://technspire.com/en/blog/prompt-caching-2026-real-cost-wins) — cross-provider discount comparison — accessed 2026-08-01
- [Anthropic Message Batches API — 50% discount, compounding with caching](https://platform.claude.com/docs/en/build-with-claude/batch-processing) — accessed 2026-08-01
- [RouteLLM: An Open-Source Framework for Cost-Effective LLM Routing — LMSYS](https://www.lmsys.org/blog/2024-07-01-routellm/) — ICLR 2025, published benchmark numbers — accessed 2026-08-01
- [GitHub — lm-sys/RouteLLM](https://github.com/lm-sys/routellm) — methodology and classifier approach — accessed 2026-08-01
- [Fault Tolerance Patterns: Circuit Breaker, Bulkhead, Retry](https://system-design.space/en/chapter/resilience-patterns/) — retry/fallback semantics referenced from `T21-resilience-catalogue` — accessed 2026-08-01

## Changelog
- 2026-08-01 — created
