# Guardrails In/Out: Guardrails AI, NeMo, Validation Layers, PII, Toxicity

> **Track:** T07 Agentic AI · **Time:** 2.5h · **Prereqs:** none · **Updated:** 2026-08-01
> **Module id:** `T07-guardrails` · **Tags:** security,critical

## The 30-second version

A guardrail is a check that sits before the model (input) or after it (output), and the two catch structurally different things: an input guardrail can stop a known-bad request from ever reaching the model, but it cannot see what the model would have generated; an output guardrail can catch a bad generation, but by definition the model already produced it, and if the model already called a tool or leaked data as a side effect before the check ran, the guardrail is checking a symptom after the damage is done. The stack is layers, not one filter: schema validation, PII detection and redaction, toxicity/safety classification, topical restriction, jailbreak detection, and groundedness checks each catch a different failure and each costs latency, real numbers, from under 10ms for a regex schema check to 200-800ms for an LLM-based validator, with a validator calling an auxiliary model adding 15-40% to your provider bill. The metric that decides whether any of this survives contact with real users is the false-positive rate, not the catch rate, because a guardrail that blocks 5-15% of legitimate traffic trains users to route around it or complain loudly, and a stack that fails closed on every classifier timeout will take your whole product down with the classifier. Guardrails are theatre when they wrap only the final text response on a system where the actual leak already happened through a tool call, a log line, or a side channel the filter never sees — output filtering catches what the model *says*, not what the agent *did*.

## Why this gets asked

Because you've done OWASP remediation and know that "add a WAF rule" is not the same statement as "the vulnerability is fixed," and the interviewer wants to know whether that same discipline transfers to LLM guardrails. They've usually watched a guardrail rollout go one of two bad ways: version one had no output filtering and a customer got a hallucinated refund policy that legal had to walk back, or version two added an aggressive input classifier that started blocking one in eight legitimate support messages within a week and got quietly disabled in a hotfix, at which point nobody remembered to re-enable it. They're checking whether you'll reach for "add a guardrail" as a magic fix, or whether you'll ask what specifically it catches, what it costs, and what happens when it's wrong.

---

## Lineage: past → present → future

**What came before.** The earliest LLM safety layer was the system prompt itself — "do not discuss X, do not reveal Y" — inherited directly from the assumption, wrong as `T07-agent-safety` establishes, that instructions in the prompt are enforceable the way code is. When that failed publicly (jailbreaks, DAN-style prompts, extraction attacks through 2022-2023), the industry's first structural response was output-side content moderation borrowed wholesale from the trust-and-safety stack built for user-generated content platforms: a toxicity classifier bolted onto the end of generation, the same shape as a comment-moderation filter on a forum. The pain that exposed this as insufficient was specific: those classifiers were trained on human-written toxic content and missed LLM-specific failure modes entirely — a hallucinated but perfectly polite factual claim, a jailbreak that produced harmful content phrased as fiction, a PII leak phrased as helpful customer service. Toxicity alone was the wrong single axis.

**Where it stands now.** The consensus architecture is layered and bidirectional: input rails (jailbreak/injection detection, topical scoping, PII detection before it reaches the model at all) and output rails (toxicity, PII redaction, groundedness against source documents, schema validation for structured output), with each layer owned by a different mechanism because no single classifier covers all of it. `NeMo Guardrails` (NVIDIA, current release v0.21.0 as of March 2026) implements this as a programmable rail system — input, output, dialog, retrieval, and execution rails — running in-process against your own infrastructure. `Guardrails AI` took the opposite shape: a Python validator framework built around Pydantic schemas, with a Hub of 50+ pluggable validators (PII, toxicity, regex, competitor mentions, `ValidChoices`, `ValidURL`) that wrap a `Guard` object around your LLM call and retry on validation failure. `Llama Guard` (Meta) is a classifier model, not a framework — you send it text, it returns safe/unsafe plus a category code, and Meta reports roughly a third the false-positive rate of a GPT-4-based approach on their benchmark. The cloud platforms shipped managed equivalents: AWS Bedrock Guardrails as a configurable content-policy layer callable via `ApplyGuardrail` against any model, Azure AI Content Safety with a notably more granular jailbreak/indirect-injection detector (Prompt Shields) plus groundedness detection against source documents, and Google's Model Armor for prompt/response inspection. The live disagreement is architectural, not about individual tools: whether guardrails belong inside the harness as middleware hooks (LangChain's `wrap_model_call`) that developers compose themselves, or as an external, vendor-managed gateway that every request passes through regardless of framework. The gateway approach is more uniform and auditable across a multi-team org; the middleware approach is faster and has full context (it can see the assembled prompt, not just the wire-level text).

**Where it's heading.** High confidence: **groundedness checking becomes standard for anything RAG-backed**, because it's the one guardrail category that directly targets hallucination (LLM09) with a deterministic-ish check (does the claim trace to a retrieved source) rather than a fuzzy classifier judgment, and Azure's productization of it suggests it's moving from research pattern to checkbox feature. Medium confidence: **guardrail-stack composition tooling matures** (a rule engine that routes a given request to the right combination of PII/jailbreak/groundedness checks rather than running every check on every request), because running everything on everything is the pattern producing the worst-case 200-800ms latency numbers cited below, and most requests don't need most checks. Speculative, flag it: any claim that a guardrail stack, however layered, closes prompt injection or hallucination to zero — per `T07-agent-safety`, no such structural fix exists, and vendors marketing guardrails as "solving" these problems should be read the way you'd read a WAF vendor claiming to "solve" SQL injection.

---

## Mental model

```
                    INPUT RAILS                          OUTPUT RAILS
   user/tool  ──▶  [schema][PII][jailbreak][topic]  ──▶ MODEL ──▶  [PII redact]
   input             detect       detect     scope                [toxicity]
                                                                   [groundedness]
                                                                   [schema]      ──▶ response

   WHAT EACH SIDE CAN AND CANNOT SEE
   ───────────────────────────────────────────────────────────────────────────
   INPUT rail sees:  the request BEFORE generation
     catches: malformed input, known jailbreak phrasing, PII in the prompt,
              off-topic requests
     misses:  anything only visible in what the MODEL WOULD generate —
              a subtle hallucination, a leak that emerges from the model's
              own reasoning rather than from the input

   OUTPUT rail sees: the response AFTER generation (or a tool's side effect,
                     IF you wired that in — most stacks only see the TEXT)
     catches: toxic/unsafe generated text, PII in the response, schema
              violations, ungrounded claims
     misses:  a tool call already executed. A DB write already committed.
              An email already sent. THE MODEL'S TEXT RESPONSE IS NOT
              THE ONLY OUTPUT OF AN AGENT.

   ⇒ THE GUARDRAILS-AS-THEATRE FAILURE:
     agent reads private data → calls send_email(leaked_data) → tool executes
     → THEN the text-response guardrail runs on "Email sent successfully."
     The filter is clean. The leak already happened. It never saw the tool call.
```

The one thing to internalize: **a guardrail wrapping the chat response is not a guardrail on the agent.** For anything with tools, the guardrail has to sit at the tool-call boundary (which is the harness's permission engine, `T07-harness-engineering` component 5) as well as the text boundary, or it's auditing the wrong artifact.

---

## How it actually works

### The layers, what each catches, what each misses

| Layer | Catches | Misses |
|---|---|---|
| **Schema validation** | Malformed structured output (bad JSON, wrong enum value, missing required field) | Anything schema-valid but wrong — a correctly-typed hallucinated fact passes cleanly |
| **PII detection & redaction** | Named entities matching PII patterns (SSNs, emails, phone numbers, names via NER) | Novel or context-dependent PII (a project codename that's sensitive only in context), and anything already exfiltrated via a tool call rather than the text response |
| **Toxicity/safety classifiers** | Overtly harmful, hateful, or unsafe language | Harm phrased politely (a confidently wrong medical claim), harm phrased as fiction/hypothetical (a known jailbreak vector) |
| **Topical restriction** | Requests/responses outside an approved domain (a banking bot asked for medical advice) | A request that's on-topic but still wrong or manipulated |
| **Jailbreak detection** | Known jailbreak patterns, role-play framing, "ignore instructions" phrasing | Novel phrasings not in the classifier's training distribution — this is an adversarial cat-and-mouse game, not a solved detector |
| **Groundedness checks** | Claims not traceable to retrieved source documents (the core hallucination catch for RAG) | Hallucinations in non-RAG generation with nothing to ground against |

### Tooling, concretely

`[Guardrails AI vs NeMo Guardrails: Complete Comparison 2026](https://is4.ai/blog/our-blog-1/guardrails-ai-vs-nemo-guardrails-comparison-2026-352) — accessed 2026-08-01`

- **NeMo Guardrails** (NVIDIA, v0.21.0, March 2026): programmable rails defined in Colang, running as in-process logic against your own infra — no mandatory external API call. Achieves under 50ms per check on GPU for its native rail types. Strong at dialog-flow control (steering the conversation away from a topic entirely, not just blocking one message).
- **Guardrails AI**: a `Guard` wraps your LLM call, built from a Pydantic model or JSON Schema, with validators attached per field pulled from the Guardrails Hub (50+ validators: `PIIFilter`, `ToxicLanguage`, `ValidChoices`, `ValidURL`, `NoRefusal`, regex, competitor-mention checks). On validation failure it can auto-retry the generation. Latency: 50-200ms for simple validators, 100-200ms for ML-based ones, and it explicitly supports LLM-based validators that add 200-800ms and roughly 15-40% to provider cost per turn.
- **Llama Guard** (Meta): a standalone classifier model, not a framework — send it text, get safe/unsafe plus a taxonomy category back. Meta reports about a third the false-positive rate of a GPT-4-based safety check on their internal benchmark. General Analysis's 2026 benchmark measured Llama Guard 4's p95 latency around 459ms on typical GPU hardware, which is not negligible if it's in the hot path of every turn.
- **Cloud-managed**: AWS Bedrock Guardrails (a configurable policy layer via `ApplyGuardrail`, model-agnostic but AWS-hosted); Azure AI Content Safety (content filtering with severity thresholds, Prompt Shields for jailbreak and *indirect* injection detection specifically, groundedness detection against source docs, protected-material/copyright detection); Google Model Armor (prompt/response inspection and safety filtering). A common production pattern composes across vendors — e.g. Bedrock for PII, Azure Content Safety for jailbreak detection, a third-party groundedness scorer — because no single vendor covers every layer equally well.

### The latency and cost budget, with numbers

Industry guidance converges on **sub-100ms p50 for the input rail and sub-150ms p50 for the output rail** as the point where guardrails stay invisible to the user; **200ms p50 is the threshold where the guardrail stack itself becomes the product's latency bottleneck**, ahead of the model call on a fast model. Concretely, stacking checks compounds fast:

- Simple regex/schema check: under 10ms.
- Guardrails AI ML-based validator: 50-200ms.
- NeMo Guardrails native rail on GPU: under 50ms.
- Llama Guard 4: ~459ms p95.
- An LLM-based validator (calling an auxiliary model to judge the output): 200-800ms, and this is where cost also spikes — 15-40% added to the provider bill per turn, before accounting for the extra round trip's own latency.
- Chaining multiple validators in series can roughly double the perceived latency versus running the cheapest one alone, because most stacks don't parallelize by default.

Effectiveness numbers from the same body of benchmarking: guardrail frameworks catch **60-85% of problems a human reviewer would classify as serious**, and produce **false positives on 5-15% of turns**. Neither number is close to 100/0, which is exactly why the next section matters more than the catch rate.

### False-positive rate: the metric that decides survival

A guardrail's catch rate is what you optimize in a demo. Its false-positive rate is what determines whether it survives being turned on for real users. At 5-15% false positives (the measured industry range), a chatty support bot blocking one in ten legitimate messages generates a support ticket about the support bot, and the operational response is almost always the same: someone loosens the threshold under pressure, and nobody re-tightens it once the complaints stop, silently eroding the protection back toward zero. The concrete practice: track false-positive rate as a first-class dashboard metric next to catch rate, segment it by request type (a banking topic-restriction guardrail will have a very different FP profile on "what's my balance" than on "explain compound interest"), and treat "we tightened the threshold" as a change that needs the same before/after measurement as any other production change, not a one-time tuning pass.

### Fail-open vs. fail-closed

When the guardrail service itself errors — the classifier times out, the PII service is down — you have to choose what happens to the request in flight, and the choice is domain-specific, not a framework default:

- **Fail-closed** (block the request when the guardrail can't run): correct for anything regulated or high-stakes — healthcare, finance, anything where an unfiltered response could create legal exposure. The principle: if you can't prove the output is safe, don't send it, even if that means an outage.
- **Fail-open** (let the request through when the guardrail can't run): correct when availability matters more than the marginal risk of one unchecked response, typically for low-stakes internal tools or when the guardrail is a secondary layer behind a stronger primary control (like a permission engine that would block the dangerous action anyway).

The mistake is not picking wrong, it's not picking at all and inheriting whatever the library defaults to — most open-source guardrail libraries default to fail-open because that's the choice that doesn't page anyone at 3am, which is precisely the wrong default for a regulated workload.

### When guardrails are theatre

The clearest case: an output filter scanning the assistant's final chat message for PII, running in a system where the agent has already called a tool that wrote the same PII to an external log, a third-party API, or a `send_email` call earlier in the same turn. The filter reports clean because it only ever looked at the text the user will read; the leak happened through a side channel the filter has no visibility into. This is the direct consequence of the mental-model point above: **guardrails on the text channel do not cover the tool-call channel**, and an agent's dangerous outputs are increasingly the tool calls, not the prose. The fix is not a better text filter, it's extending the guardrail concept to the tool-call boundary itself — which in practice means the permission engine (`T07-harness-engineering`) is doing the real work, and the "guardrail" product is covering the smaller, decreasingly relevant surface.

---

## Build it from scratch

```python
# untested sketch - illustrates the two-sided rail shape, not a library
import re, time

def input_rails(request: str) -> tuple[bool, str]:
    # cheap checks first: schema/regex before anything ML-based
    if len(request) > 20_000:
        return False, "Error: request exceeds size limit."
    if re.search(r"ignore (all|previous|prior) instructions", request, re.I):
        return False, "Error: request flagged by jailbreak heuristic."
    pii_hit = detect_pii(request)          # e.g. a Presidio-style NER + regex pass
    if pii_hit:
        request = redact(request, pii_hit)  # redact, don't necessarily block
    return True, request

def output_rails(response: str, sources: list[str], budget_ms: int = 150) -> tuple[bool, str]:
    t0 = time.monotonic()
    ok, response = schema_check(response)              # ~1-10ms
    if not ok:
        return False, "Error: response failed schema validation."
    pii_hit = detect_pii(response)                      # ~10-50ms
    if pii_hit:
        response = redact(response, pii_hit)
    if (time.monotonic() - t0) * 1000 > budget_ms:
        # ran out of latency budget: SKIP the expensive groundedness check
        # rather than silently blocking -- this is a FAIL-OPEN decision,
        # made explicitly, logged, and alerted on, not a silent default.
        log_budget_exceeded("output_rails")
        return True, response
    grounded = groundedness_check(response, sources)    # 200-800ms if LLM-based
    if not grounded:
        return False, "Error: response not grounded in provided sources."
    return True, response

def tool_call_rail(call_name: str, call_args: dict, perms) -> bool:
    # THE PART TEXT-ONLY GUARDRAIL STACKS MISS: gate the tool call itself,
    # not just the text response that describes it afterward.
    return perms.resolve(call_name, call_args) == "allow"
```

The lab-worthy exercise: build a fake agent that leaks a secret via a tool call and produces an innocuous text summary ("data exported successfully"), run only `output_rails` against the text and show it passes clean, then add `tool_call_rail` and show it's the one that actually stops the leak. That's the guardrails-as-theatre failure made concrete and testable.

---

## How it's done in production

**Failure-mode table**

| Symptom | Cause | Fix |
|---|---|---|
| Text response is clean but sensitive data left the system anyway | Output guardrail only inspects the chat response, not tool calls or side effects | Add a permission/rail check at the tool-call boundary; treat text filtering as one layer among several, not the whole stack |
| Guardrail stack adds 400-600ms and users complain about latency | Every check running on every request, including expensive LLM-based validators for low-risk turns | Route by risk: cheap schema/regex checks always-on, expensive groundedness/LLM-judge checks only for high-stakes categories or RAG-backed answers |
| False-positive complaints rising, thresholds keep getting loosened under pressure | No FP-rate dashboard; tuning is reactive and one-directional | Track FP rate as a first-class metric segmented by request type; require a measured before/after for any threshold change |
| A guardrail vendor outage takes down the whole product | Fail-closed applied uniformly, including to low-stakes internal paths that didn't need it | Set fail-open/fail-closed per use case, not globally; regulated/high-stakes paths fail-closed, everything else fails open with logging |
| Guardrail passes, then a groundedness audit months later finds systematic hallucination in a RAG feature | No groundedness check was ever wired in; toxicity/PII checks don't touch factuality at all | Add groundedness checking specifically for RAG-backed answers; it's the one layer that targets hallucination directly |
| Jailbreak detector catches last year's attacks, misses this year's | Static classifier, no update cadence, no red-team feedback loop | Treat the jailbreak/injection detector like a WAF ruleset: needs ongoing red-team input (see `T07-agent-safety`, `T07-harness-evals`) and periodic retraining/retuning |

---

## Tradeoffs & when NOT to use it

- **Don't run every layer on every request.** A guardrail stack is a cost and latency budget, not a checkbox to max out. If your product is a low-stakes internal tool with no external users and no regulated data, a full six-layer stack at 200-800ms per turn is the wrong trade; schema validation plus basic PII redaction may be the entire justified budget.
- **Don't treat an output filter as sufficient for an agent with tools.** If the dangerous surface is what the agent *does* (send an email, write a record, call an API) rather than what it *says*, the guardrail belongs at the tool-call boundary, and a text-only filter is decorative for that threat model — this is the theatre case, and it's common enough to name explicitly in review.
- **Don't default to fail-open on a regulated workload just because it's the library default.** Healthcare, finance, and anything with legal exposure from an unfiltered response needs an explicit fail-closed decision, accepted as an availability tradeoff up front, not discovered during an incident review.
- **Don't chase catch rate past the point where false positives make the product unusable.** A guardrail at 95% catch and 20% false-positive rate is very likely worse for the business than one at 80% catch and 5% false-positive, because the false positives are guaranteed daily friction and the missed catches are probabilistic tail risk — model this as an expected-cost tradeoff, not a leaderboard score.
- **When a permission engine already blocks the dangerous action, a redundant output-side guardrail for that same action is diminishing returns.** Spend the latency budget on the layer that doesn't yet have coverage.

---

## Interview questions

### Q1 — What's the structural difference between an input guardrail and an output guardrail, and why do you need both?
**Testing:** whether "guardrails" is one undifferentiated concept or two with different blind spots.
**Answer:** Input rails see the request before generation and can block known-bad patterns before they reach the model, but can't see what the model would have generated. Output rails see the actual response (or should also see tool calls) and can catch bad generations, but only after they've happened — if the bad thing was a tool call with a side effect, the damage occurred before the check ran.
**Follow-up trap:** *"So output rails are strictly better since they see the real result?"* No — for anything with side effects, "after it happened" is too late; the check needs to sit at the point of consequence (the tool call), not after the fact on the text summary.

### Q2 — Your output guardrail scans for PII in the response text and reports clean, but a customer's SSN still leaked. Diagnose.
**Testing:** the guardrails-as-theatre concept, directly.
**Answer:** The SSN almost certainly left through a channel the guardrail never inspected — a tool call (an email, an API write, a log line) rather than the final chat text. A guardrail wrapping only the assistant's response is auditing a shrinking fraction of an agent's actual output surface.
**Follow-up trap:** *"Add PII scanning to every tool call's arguments then?"* That's the right direction, but frame it correctly: at that point you're building a permission/validation layer at the tool boundary, which is a harness concern (`T07-harness-engineering`), not an incremental guardrail feature — say that explicitly rather than describing it as "more guardrails."

### Q3 — Compare NeMo Guardrails, Guardrails AI, and Llama Guard. When would you reach for each?
**Testing:** current, specific tool knowledge rather than "there are some libraries."
**Answer:** NeMo Guardrails is a programmable rail system (Colang-defined input/output/dialog/retrieval/execution rails) running in-process, sub-50ms on GPU — good for dialog-flow control and when you want everything self-hosted with no external call. Guardrails AI is a Pydantic-based validator framework with a Hub of 50+ validators, good for structured-output enforcement and composable per-field validation, at 50-200ms for simple validators. Llama Guard is a standalone safety classifier, not a framework — you call it, it returns safe/unsafe plus a category, useful as one input or output rail among several, not a full pipeline.
**Follow-up trap:** *"Pick one and standardize on it."* Push back: production stacks commonly compose across these (e.g. Llama Guard as a fast first-pass classifier, NeMo for dialog control, Guardrails AI for output schema enforcement) because no single tool covers every layer equally well.

### Q4 — Give me real latency numbers for a guardrail stack. What's the budget you'd design to?
**Testing:** numbers-over-adjectives discipline.
**Answer:** Sub-100ms p50 for the input rail, sub-150ms p50 for output, with 200ms p50 as the threshold where the guardrail stack itself becomes the bottleneck. Concretely: schema/regex under 10ms, Guardrails AI ML validators 50-200ms, NeMo native rails under 50ms on GPU, Llama Guard 4 around 459ms p95, and any LLM-based validator 200-800ms plus 15-40% added provider cost.
**Follow-up trap:** *"Your groundedness check alone is 600ms and you have a 150ms budget. What do you do?"* Don't silently skip it — either move it off the critical path (async, with the unverified response flagged rather than blocking), restrict it to only RAG-backed answers where it matters most, or accept the latency for that specific category and say so explicitly, logged as a deliberate tradeoff.

### Q5 — What single metric tells you whether a guardrail should stay enabled?
**Testing:** whether catch rate or false-positive rate is understood as the operative metric.
**Answer:** False-positive rate. Catch rate is what you tune in a demo; false-positive rate, at the industry-typical 5-15%, is what determines whether real users get blocked often enough to route around the guardrail or generate support load that gets it disabled under pressure.
**Follow-up trap:** *"Isn't missing a real attack worse than annoying a few users?"* Per-incident, yes; in aggregate, a guardrail nobody trusts because it fires on legitimate traffic gets its threshold loosened or gets disabled entirely, which erases the catch rate too — the FP rate is what determines whether the protection survives, not just how annoying it is.

### Q6 — Fail-open or fail-closed when your PII classifier times out?
**Testing:** whether the decision is domain-driven or reflexive.
**Answer:** Depends on the domain, and it must be an explicit choice, not a library default. Fail-closed for healthcare, finance, or anything with legal exposure — if you can't prove the output is safe, don't send it. Fail-open for low-stakes internal tools where availability matters more, especially when a stronger downstream control (a permission engine) would catch the actually dangerous cases anyway.
**Follow-up trap:** *"Most open-source guardrail libraries default to fail-open. Why is that dangerous?"* Because it's the choice that avoids paging anyone at 3am, which is exactly backwards for a regulated workload — teams inherit this default without realizing they made a compliance decision by not making one.

### Q7 — Design the guardrail stack for a RAG-backed customer support agent.
**Testing:** whether they can compose layers to an actual threat model rather than listing every tool.
**Answer:** Input: schema/size check (cheap, always on), PII detection on the incoming message (redact before it enters context if the workflow doesn't need it), lightweight jailbreak heuristic. Output: PII redaction on the response, groundedness check against the retrieved documents specifically (this is the layer that catches the actual hallucination risk in a RAG system), schema validation if the response feeds a downstream system. Toxicity classification is lower priority here than groundedness, because the dominant risk in a support bot is confidently wrong information, not toxic language.
**Follow-up trap:** *"Where does the jailbreak detector run — input or output?"* Input, ideally before the request reaches the model at all, since the goal is to prevent the manipulated generation rather than catch it after the fact; but note detection is probabilistic (`T07-agent-safety`), so it's a cost-reduction layer, not the safety boundary.

### Q8 — A teammate wants to add an LLM-as-judge output validator to every single turn for quality. What do you push back on?
**Testing:** cost/latency discipline against a specific, common proposal.
**Answer:** An LLM-based validator on every turn adds 200-800ms and roughly 15-40% to the provider bill per turn — for most products that's an unacceptable tax to apply uniformly. Route it: run the expensive judge only on categories where it earns its cost (high-stakes answers, RAG-backed claims, anything that failed a cheaper check first), not as a blanket per-turn gate.
**Follow-up trap:** *"What if quality regressions are worth that cost?"* Then measure it as an A/B, not a blanket rollout — quantify the quality lift against the latency and cost hit for your specific traffic mix before deciding it's worth it everywhere versus only on the subset where the ROI is clear.

### Q9 — Groundedness checking: what does it actually verify, and what can't it catch?
**Testing:** precision on a specific, increasingly standard layer.
**Answer:** It verifies that claims in the response trace back to the retrieved source documents provided to the model — the core defense against RAG-specific hallucination. It can't catch hallucination in non-RAG generation (there's nothing to ground against), and it can't catch a claim that's technically traceable to a source but the source itself is wrong or outdated.
**Follow-up trap:** *"So groundedness solves hallucination for RAG apps?"* No — it solves *fabrication*, not *misinterpretation*. A response can be perfectly grounded in a real source and still misstate what that source says; groundedness is necessary, not sufficient, for factual accuracy.

### Q10 — When would you deliberately choose NOT to add a guardrail layer that's technically available and cheap?
**Testing:** the required real "when NOT to use this."
**Answer:** When the layer duplicates coverage a stronger control already provides — e.g. a text-response PII filter behind a system where the agent has no tool that could leak PII in the first place, or a topical-restriction rail on an internal tool used by five engineers who already understand its scope. Every layer has an ongoing cost (latency, false positives, maintenance as attack patterns shift), and "it's available" isn't sufficient justification against a threat model that doesn't need it.
**Follow-up trap:** *"Isn't more coverage always safer, even if redundant?"* Not once you account for false-positive fatigue: redundant layers each contribute their own FP rate, compounding the odds a legitimate request gets blocked somewhere in the stack, for a marginal safety gain against a risk that's already covered.

### Q11 — Your jailbreak detector was state-of-the-art at launch. A year later, attack success rate against it has crept up. Why, and what do you do?
**Testing:** understanding that guardrail effectiveness decays like an appsec ruleset, not a one-time investment.
**Answer:** Jailbreak/injection classifiers are adversarial targets, and attackers iterate against known detectors the same way they iterate against WAF rules — a static classifier's effective catch rate decays as new phrasings are discovered and shared. Treat it operationally like a WAF: feed it red-team results (`T07-agent-safety`, `T07-harness-evals`) on a cadence, retrain or retune the threshold, and track the metric over time rather than treating the initial benchmark score as permanent.
**Follow-up trap:** *"Can you ever stop updating it?"* No — this is a maintenance commitment, not a one-time integration, and teams that budget it as the latter are the ones who get surprised by drift.

---

## Red flags that fail you

- Describing "add a guardrail" as if it were a single, complete mitigation rather than naming which layer and what it specifically catches.
- Claiming an output filter on the chat response covers an agent's tool calls.
- Not knowing false-positive rate as the metric that determines whether a guardrail survives in production.
- Treating fail-open/fail-closed as a framework default rather than a per-domain decision.
- No latency or cost numbers when asked to design a guardrail stack.
- Calling a jailbreak or injection classifier "solved" rather than an ongoing, decaying detector.
- Recommending every layer on every request with no routing by risk.

## Cheat card

```
INPUT RAIL sees request BEFORE generation. OUTPUT RAIL sees response AFTER.
  input catches: malformed input, known jailbreak phrasing, PII in prompt
  output catches: toxic/unsafe text, PII in response, ungrounded claims
  BOTH miss: a TOOL CALL side effect. Text filters don't see what the agent DID.

LAYERS (each catches ONE thing)
  schema validation   -> malformed structured output
  PII detect/redact    -> named-entity PII patterns
  toxicity classifier  -> overtly harmful language (not polite wrong answers)
  topical restriction  -> off-domain requests
  jailbreak detection  -> KNOWN attack patterns (adversarial, decays over time)
  groundedness check   -> claims not traceable to RAG sources (hallucination)

LATENCY BUDGET (know cold)
  schema/regex          <10ms
  NeMo native rail (GPU) <50ms
  Guardrails AI validator 50-200ms
  Llama Guard 4 p95      ~459ms
  LLM-based validator    200-800ms, +15-40% provider cost
  design target: input p50 <100ms, output p50 <150ms, 200ms = bottleneck

EFFECTIVENESS (industry range)
  catch rate: 60-85% of human-flagged-serious problems
  false positives: 5-15% of turns  <- THE METRIC THAT DECIDES SURVIVAL
  FP rate too high -> thresholds get loosened under pressure -> protection erodes

FAIL-OPEN vs FAIL-CLOSED — explicit per-domain choice, never a library default
  fail-closed: regulated/high-stakes (healthcare, finance, legal exposure)
  fail-open:   low-stakes, or a stronger downstream control already covers it
  most OSS libs default fail-open (avoids 3am pages) -- wrong default for regulated

TOOLS
  NeMo Guardrails v0.21.0 (Mar 2026): Colang rails, in-process, <50ms GPU
  Guardrails AI: Pydantic Guard + Hub (50+ validators), 50-200ms
  Llama Guard: classifier model, ~1/3 the FP rate of GPT-4-based check (Meta)
  cloud: AWS Bedrock Guardrails · Azure Content Safety (Prompt Shields,
         groundedness) · Google Model Armor

GUARDRAILS-AS-THEATRE
  agent leaks data via tool call -> text summary says "success" -> output
  filter scans the CLEAN TEXT and passes. Fix: gate the TOOL CALL boundary
  (permission engine), not just the chat response.

WHEN NOT TO ADD A LAYER
  duplicate coverage a stronger control already provides
  low-stakes surface with no matching threat model
  every added layer compounds false-positive odds across the whole stack
```

## Sources

- [Best AI Agent Guardrails Platforms in 2026: 6 Tools Compared](https://futureagi.com/blog/best-ai-agent-guardrails-platforms-2026/) — accessed 2026-08-01
- [Guardrails AI vs NeMo Guardrails: Complete Comparison 2026](https://is4.ai/blog/our-blog-1/guardrails-ai-vs-nemo-guardrails-comparison-2026-352) — accessed 2026-08-01
- [Benchmarking LLM Guardrail Providers: A Data-Driven Comparison](https://www.truefoundry.com/blog/benchmarking-llm-guardrail-providers) — latency/cost figures for LLM-based validators; accessed 2026-08-01
- [LLM guardrails: frameworks and their real cost](https://jacar.es/en/llm-guardrails-frameworks-and-their-real-cost/) — p50 latency thresholds, catch rate and false-positive industry ranges; accessed 2026-08-01
- [The Ultimate Guide to LLM Guardrails (2026)](https://futureagi.com/blog/ultimate-guide-llm-guardrails-2026/) — accessed 2026-08-01
- [AI Agent Guardrails: NeMo, LlamaGuard & Safety Layers (2026)](https://cowork.ink/blog/ai-agent-guardrails/) — Llama Guard false-positive comparison vs GPT-4-based check; accessed 2026-08-01
- [Best AI Guardrails in 2026: Tools, Architecture, and How to Choose](https://generalanalysis.com/guides/best-ai-guardrails) — Llama Guard 4 p95 latency benchmark; accessed 2026-08-01
- [Top 5 Platforms to Implement AI Guardrails in 2026](https://www.getmaxim.ai/articles/top-5-platforms-to-implement-ai-guardrails-in-2026/) — AWS Bedrock Guardrails, Azure AI Content Safety, Google Model Armor feature comparison; accessed 2026-08-01
- [Generate Structured Data — Guardrails AI docs](https://www.guardrailsai.com/docs/how_to_guides/generate_structured_data) — Guard/Pydantic architecture; accessed 2026-08-01
- `curriculum/07-agentic-ai/14-agent-safety.md` (`T07-agent-safety`) — threat landscape guardrails defend against
- `curriculum/07-agentic-ai/25-harness-engineering.md` (`T07-harness-engineering`) — permission engine as the tool-call-boundary control guardrails cannot replace

## Changelog
- 2026-08-01 — created
