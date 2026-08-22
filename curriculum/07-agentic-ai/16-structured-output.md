# Structured Output: JSON Schema, Constrained Decoding, Repair Loops

> **Track:** T07 Agentic AI · **Time:** 2.0h · **Prereqs:** none · **Updated:** 2026-08-01
> **Module id:** `T07-structured-output` · **Tags:** production,critical

## The 30-second version

There are three ways to get an LLM to emit valid JSON, and they trade off differently: prompting-and-hoping produces syntactically invalid output some non-trivial fraction of the time and requires a repair loop as a load-bearing part of the design, not a fallback; tool/function-calling schemas turn the model's output into a structured argument the API validates, which is what most providers actually mean by "structured outputs" today and is the right default; and constrained decoding masks the logits at every token so an invalid token is literally impossible to sample, which is a stronger guarantee than either but comes with a real, published, senior-level cost — forcing the shape can measurably degrade reasoning quality by 10-30% on tasks where the model needs to think before it commits to an answer field. Shape and correctness are different properties: a schema validator checks that `email` is a string, not that the string in `email` is actually the customer's email and not their name field with the labels swapped, and that failure mode passes every schema check while being silently wrong. Structured output is a solved shape problem and an unsolved semantics problem, and the senior answer says both halves out loud.

## Why this gets asked

Because "just use JSON mode" is the kind of answer that sounds complete and isn't, and the interviewer has debugged a production incident where the JSON was perfectly valid and completely wrong — a form-filling agent that swapped `billing_address` and `shipping_address` because both are strings and the schema had no way to know which was which. They're checking whether the candidate understands that constraining *shape* is a narrower, easier, and mostly-solved problem than guaranteeing *correctness*, and whether they know the actual mechanism (logit masking, not "the model is told to output JSON") well enough to reason about its side effects rather than just its guarantee.

---

## Lineage: past → present → future

**What came before.** The earliest approach to structured output was pure prompting: tell the model "respond only with valid JSON matching this schema" and parse whatever comes back, with a regex or a lenient parser trying to salvage near-misses (trailing commas, markdown code fences wrapping the JSON, an explanatory sentence before the braces). This failed often enough to be a running joke in early LLM-application engineering, and the failure mode was expensive precisely because it was silent at the code level — a parse error is loud, but a successfully-parsed object with a hallucinated extra field or a subtly wrong type coercion is not. The first real fix was function/tool calling (OpenAI's `functions` parameter, later generalized across providers): instead of asking the model to write JSON as text, give it a schema as a first-class API construct and let the model populate structured arguments, which moved schema adherence from "prompt engineering" to "API contract."

**Where it stands now.** Two mechanisms now coexist as production defaults, and providers differ on which they lead with. OpenAI's Structured Outputs (`strict: true`, `additionalProperties: false`) constrains the JSON response format directly and reports failure rates below 0.1% on their own benchmarks — a real engineering achievement built on genuine grammar-constrained decoding under the hood. Anthropic's primary mechanism is tool use with `strict: true` on the tool definition, delivering comparably high reliability without exposing a separate "JSON mode" concept — as of this writing Claude does not support a `json_schema` response format the way OpenAI does, and the tool-use path is the documented route. Separately, and mostly in self-hosted/open-model deployments, **constrained decoding libraries** (Outlines, XGrammar) implement the mechanism from first principles: compile the schema into a finite-state machine or pushdown automaton, and at every decoding step mask the logits so only grammar-valid tokens are eligible for sampling — a materially stronger guarantee than API-level structured outputs because it operates on the actual sampling distribution rather than on a post-hoc validation-and-retry loop. The live disagreement is exactly the finding this module centers on: a growing body of evidence (Tam et al. 2024, and follow-up work through 2026) shows that forcing structure via constrained decoding measurably degrades reasoning-heavy task performance, and the field has not converged on when that tradeoff is worth it.

**Where it's heading.** Two threads, different confidence levels. **Interleaved-reasoning-then-structure is winning as the mitigation** — let the model reason freely in prose or a thinking block, then extract or constrain only the final answer into a schema, rather than constraining the entire generation from the first token; this is high confidence because it directly targets the documented mechanism of the degradation (constraints applied *before* reasoning completes are what hurts) and multiple independent groups have converged on it. **Schema-aware training** — models fine-tuned to be good at structured generation without needing external constraint at all — is a plausible direction but still emerging, and treating it as solved would be premature; today's frontier models still benefit measurably from either tool-calling schemas or post-hoc validation, they don't reliably self-constrain.

---

## Mental model

```
                    THREE MECHANISMS, INCREASING GUARANTEE STRENGTH

  PROMPT-AND-HOPE              TOOL/FUNCTION SCHEMA           CONSTRAINED DECODING
  ──────────────────           ─────────────────────          ─────────────────────
  "Output valid JSON           Schema is an API-level          Grammar compiled to an
  matching this shape"         construct; model populates      FSM/PDA; logits MASKED
  as plain text in the         a structured "tool call"        at every decode step so
  prompt.                      argument the API validates.     invalid tokens can't be
                                                                 sampled AT ALL.
  Guarantee: none.             Guarantee: high (<0.1%           Guarantee: absolute on
  Failure mode: malformed      reported failure rate on         SHAPE.
  JSON, needs a repair         strict modes) but still a
  loop as core design,         model-cooperation contract,      Cost: can measurably
  not a fallback.              not a hard sampling constraint.  degrade REASONING quality
                                                                 (10-30% on some tasks) —
                                                                 masking high-probability
                                                                 tokens the model "wanted"
                                                                 renormalizes the rest,
                                                                 amplifying differences and
                                                                 sometimes forcing an
                                                                 answer field before the
                                                                 model finished thinking.
```

The one thing to internalize: **all three mechanisms guarantee shape with different strength; none of them guarantee correctness.** A JSON object that perfectly validates against your schema can still have the customer's name in the `email` field if both are typed as strings and the model confused the two source spans during extraction — the validator has no way to know, because the schema describes structure, not semantics, and nothing in any of these three mechanisms checks the latter.

---

## How it actually works

### Mechanism 1: prompting-and-hoping

```python
# untested sketch — the failure-prone baseline, shown to be explicit about what it lacks
prompt = f"""Extract the name and email from this text. Respond with ONLY valid JSON
matching this shape: {{"name": "string", "email": "string"}}

Text: {text}"""
response = model.generate(prompt)
data = json.loads(response)  # throws on: markdown fences, trailing commentary,
                              # trailing commas, an apologetic preamble, truncated
                              # output at max_tokens
```

This is not a strawman — it is still common in low-stakes internal tooling, and it is a legitimate choice *if* you build the repair loop as a first-class part of the design rather than an afterthought, because the failure rate is real and non-trivial across models and prompt styles. The mistake is treating `json.loads()` wrapped in a bare `try/except` as sufficient; it is the first attempt in a retry strategy, not the whole strategy.

### Mechanism 2: tool/function-calling schemas

The model emits its answer as a structured tool-call argument rather than as free text the caller must parse. This is the mechanism both Anthropic and OpenAI treat as primary today, though they expose it slightly differently:

```python
# untested sketch — Anthropic strict tool use
response = client.messages.create(
    model="claude-opus-5",
    max_tokens=1024,
    tools=[{
        "name": "extract_contact",
        "description": "Extract a contact's name and email",
        "strict": True,  # requires additionalProperties: false + full required list
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "email": {"type": "string"},
            },
            "required": ["name", "email"],
            "additionalProperties": False,
        },
    }],
    messages=[{"role": "user", "content": f"Extract from: {text}"}],
)
# response contains a tool_use block whose `input` field validates exactly
# against the schema when strict: true is set.
```

**Anthropic's `output_config.format` path** (structured outputs on the response itself, via `client.messages.parse()` with a Pydantic model) is the newer, response-level alternative to routing everything through a tool call, and it's the mechanism to reach for when the output isn't naturally framed as a tool argument. Both paths share the same underlying JSON Schema subset support and limitations (below).

**JSON Schema features that are supported:** basic types (object, array, string, integer, number, boolean, null), `enum`, `const`, `anyOf`, `allOf`, `$ref`/`$def`, and common string formats (`date-time`, `email`, `uuid`, etc.). **What commonly is not supported:** recursive schemas, numerical constraints (`minimum`, `maximum`, `multipleOf`), string length constraints (`minLength`, `maxLength`), and `additionalProperties` set to anything other than `false`. Some SDKs quietly strip unsupported constraints from the schema sent to the API and validate them client-side after the fact — which means the guarantee you think you're getting from a `maxLength: 50` constraint may actually be a client-side check running *after* generation, not a decode-time constraint at all. Always verify which layer is enforcing which part of your schema.

### Mechanism 3: constrained decoding

The mechanism that gives shape guarantees teeth. At each decoding step, the decoder computes which tokens are grammar-valid given the partial output so far, and masks every other token's logit to negative infinity before sampling — an invalid token isn't merely discouraged, it has zero probability of being selected. Outlines pioneered the general approach for arbitrary regular and context-free grammars by compiling them into finite-state machines (for regular languages/JSON schemas) or pushdown automata (for context-free grammars), with token masks precomputed offline where possible. XGrammar improved on this for production serving by partitioning the vocabulary into context-independent and context-dependent subsets, amortizing the cost of mask construction across decoding steps — this matters because naive per-token grammar checking is slow enough to meaningfully hurt throughput at serving scale, and XGrammar's optimization is specifically what makes constrained decoding viable in high-throughput settings like vLLM.

```python
# untested sketch — illustrates the mechanism, not a specific library's exact API
def masked_logits(logits: Tensor, valid_token_ids: set[int]) -> Tensor:
    mask = torch.full_like(logits, float("-inf"))
    mask[list(valid_token_ids)] = 0.0
    return logits + mask  # invalid tokens: probability zero after softmax

# at each step: valid_token_ids = fsm.get_valid_next_tokens(current_state)
```

vLLM's guided decoding, built on this kind of token-bitmask approach, is the common serving-side integration point — you declare a JSON schema and the engine builds and applies the grammar automatically per request.

### Why constrained decoding can degrade content quality — the senior insight

This is the finding worth having internalized, not just cited. Tam et al. (2024, "Let Me Speak Freely? A Study on the Impact of Format Restrictions on Performance of Large Language Models," EMNLP 2024 Industry Track) documented that strict format constraints (JSON, XML, YAML) cause a **10-30% degradation in reasoning task performance** compared to free-form generation on the same task. Two independent mechanisms drive this, and both matter for how you mitigate it:

1. **Structural forcing pre-empts reasoning.** JSON-mode constrained decoding can force the model to commit to an answer field's shape before it has finished the chain-of-thought that should produce that answer — if your schema puts the `answer` field early or doesn't leave room for intermediate reasoning inside the structure, the model is grammatically required to start emitting the answer at the point the grammar says an answer token is next, whether or not its reasoning is actually done. This is a **prompt-level** effect: how you structure the schema and where you put reasoning relative to the answer field matters as much as whether you constrain at all.
2. **Logit masking distorts the underlying distribution.** When high-probability tokens the model actually "wants" to generate are masked because they violate the grammar, the remaining valid tokens get renormalized — and renormalization can amplify relative differences among tokens the model would otherwise have judged close in probability, producing outputs that are syntactically perfect but semantically degraded relative to what the model would have said unconstrained. This is a **decoder-level** effect, present even with a well-designed schema, though later analysis (Lee et al., 2026) found the prompt-level effect dominates and the decoder-level effect is comparatively minor.

**The practical mitigation, and the one interviewers want named:** don't force structure before reasoning is complete. Let the model produce its reasoning in prose or a `thinking` block first — unconstrained — and only constrain the final extraction step, either as a separate constrained call over the already-reasoned content, or by designing the schema so free-form reasoning fields precede the structured answer fields rather than the other way around. This is the same principle behind "chain-of-thought before the final JSON block" prompting patterns that predate the formal study, now with a mechanistic explanation for why they work.

### The failure mode no validator catches

**Semantically wrong field assignment inside a valid schema.** A contract-extraction agent asked to populate `{"party_a": string, "party_b": string}` from a document can swap the two parties — every field is present, every field is the correct type, `additionalProperties` is satisfied, and the object passes strict validation completely. Nothing in JSON Schema, strict tool use, or constrained decoding checks that the *content* assigned to a field is the content that *belongs* there; they all check shape, never meaning. This is structurally the same failure as the address-swap example in the 30-second version, and it is the reason structured output should never be the last checkpoint on a high-stakes extraction pipeline — a semantic validator (a second model call verifying "does `party_a` actually correspond to the first-named party in the source text," or a deterministic cross-check against a known value) is a separate, additional layer, not something schema validation gives you for free.

### Repair loops: retry, reprompt, or fail

When output doesn't parse or doesn't validate, three responses compose into an escalation ladder:

1. **Retry** — resend the identical or near-identical request, sometimes at a higher temperature or with a fresh sample, on the theory that the failure was a one-off sampling artifact rather than a systemic misunderstanding. Cheap, works for transient glitches, does nothing for a model that's confidently wrong in the same way every time.
2. **Reprompt** — include the validation error in the next request so the model can see exactly what it got wrong (`Instructor`'s core mechanism: validate the response against a Pydantic model, and on failure, append the validation error message to the conversation and ask the model to correct it). This works because the model can often fix a specific, named error ("field 'age' expected integer, got string '25 years old'") that it wouldn't have avoided from the schema alone — the error message is new information the first attempt didn't have.
3. **Fail** — after N reprompt attempts (2-3 is typical), stop and surface a structured failure rather than looping indefinitely or accepting a best-effort malformed result. This boundary matters operationally: an unbounded reprompt loop against a model that's systematically wrong about a field is a cost and latency sink with no exit condition, and it should be bounded and monitored the same way any other loop's step cap is (see `T07-loop-engineering`).

```python
# untested sketch — Instructor's shape, illustrating the reprompt mechanism
from pydantic import BaseModel
import instructor

class ContactInfo(BaseModel):
    name: str
    email: str

client = instructor.from_provider("anthropic/claude-opus-5")
result = client.messages.create(
    response_model=ContactInfo,
    max_retries=3,  # Instructor wraps the call-validate-reprompt loop for you
    messages=[{"role": "user", "content": f"Extract from: {text}"}],
)
```

**Choosing which rung of the ladder to use:** a malformed-JSON failure (parse error) is usually worth a bare retry first, since it's often a sampling artifact rather than a misunderstanding. A schema-validation failure (parses fine, wrong type or missing field) is worth a reprompt with the specific error, since the model needs the new information to correct course. A repeated failure on the same field after 2-3 reprompts is a signal the model doesn't understand the task, not that it needs another chance — escalate to fail-and-surface, or to a human, rather than continuing to retry.

### Layer responsibilities: Pydantic, Instructor, Outlines

These three names get used loosely and interviewers probe for whether the candidate knows which layer does what:

| Layer | What it actually does |
|---|---|
| **Pydantic** | Defines the schema as Python types and validates a parsed object against it — pure Python, no model interaction at all. It's the *specification and validation* layer, agnostic to how the data got there. |
| **Instructor** | Wraps a provider's API client, converts a Pydantic model into the provider's schema format (tool schema or `output_config.format`), sends the request, validates the response against the Pydantic model, and on failure retries with the validation error appended to the conversation. It's the *orchestration* layer — the retry loop, not the constraint mechanism. |
| **Outlines / XGrammar** | Compile the schema into a grammar and mask the decoder's logits at generation time so invalid tokens cannot be sampled. This is the *constraint* layer, operating at the token level during generation, and it requires access to the model's raw logits — which means it's typically used with self-hosted serving (vLLM, SGLang) rather than a hosted API that doesn't expose that level of control. |

A production Instructor-based pipeline is doing repair-loop orchestration on top of whatever guarantee the underlying API's tool-calling or structured-output mode already provides; it is not, by itself, constrained decoding, and conflating the two in an answer is a common mistake this module exists to prevent.

### Streaming structured output

Streaming a structured response means the client receives partial, syntactically-incomplete JSON as it generates — `{"name": "Al` is not valid JSON on its own. Two practical approaches: parse with a forgiving incremental JSON parser designed for exactly this (one that can report "this is a valid prefix of a JSON value, with these fields fully resolved so far") rather than repeatedly calling a strict parser on a growing, incomplete string; or, for tool-call arguments specifically, treat the partial JSON delta stream (`input_json_delta` events) as opaque until the tool-call block closes, and only parse the complete argument once `content_block_stop` fires, sacrificing incremental UI updates for simplicity. The tradeoff is UI responsiveness (show fields as they resolve) versus implementation complexity (a parser that tolerates incompleteness); most production systems default to the simpler wait-for-complete approach unless the UI genuinely benefits from field-by-field reveal.

---

## Build it from scratch

Minimal from-scratch exercise: implement the repair-loop escalation ladder (retry → reprompt → fail) against a raw prompt-and-hope baseline with no tool schema, so the failure modes are visible without a library masking them. Then swap in a strict tool schema and observe the failure rate drop; then, if self-hosting is available, run the same extraction task through vLLM with guided decoding enabled and compare both the failure rate (should drop to effectively zero on shape) and, on a reasoning-heavy variant of the task, the answer quality (should be measurably worse than the unconstrained or tool-call versions on tasks requiring multi-step reasoning before the answer) — this is the exercise that makes the Tam et al. finding concrete rather than a fact recited from a paper.

---

## How it's done in production

**Tooling map:** Pydantic + a provider's native structured-output/tool-use mode is the default for hosted-API deployments — no self-hosting required, strong guarantees, the semantic-correctness gap is the only remaining risk to manage separately. Instructor is the standard orchestration layer on top of that when you want the retry-on-validation-failure loop handled for you across multiple providers rather than hand-rolled per provider. Outlines/XGrammar via vLLM or SGLang is the self-hosted path, reached for when you need the absolute shape guarantee constrained decoding provides (e.g., generating code or data that a downstream deterministic system will parse with zero tolerance for malformed input) and you're already running your own inference stack for other reasons — not usually adopted purely to get structured output, since the hosted-API tool-calling path already gets you most of the reliability at far less operational cost.

**What breaks at scale**

| Symptom | Cause | Fix |
|---|---|---|
| Output is valid JSON but a field contains the wrong entity's data (e.g. swapped names, swapped addresses) | Semantically wrong field assignment — no mechanism in JSON Schema, strict tool use, or constrained decoding checks content meaning, only shape | Add a separate semantic validator (a cross-check model call, or a deterministic rule) after schema validation passes; never treat schema validity as correctness |
| Reasoning-heavy extraction quality drops after switching to constrained decoding, even though shape errors go to zero | The schema forces the answer field before the model finishes reasoning, and/or logit masking distorts the sampling distribution | Let the model reason unconstrained first (prose or a thinking block), constrain only the final extraction step, or restructure the schema so free-form reasoning fields precede answer fields |
| Retry loop against a malformed response never terminates | No bounded escalation from retry to reprompt to fail | Cap reprompt attempts at 2-3, then fail loudly with a structured error rather than looping |
| A `maxLength` or `minimum` constraint in the schema is silently not enforced by the model | That constraint class isn't decode-time enforced by the provider; some SDKs strip it and validate client-side after generation | Check which layer enforces which part of the schema; don't assume every JSON Schema keyword is a hard generation-time constraint |
| Streaming UI shows a parse error mid-response | A strict JSON parser is being called repeatedly on a growing, incomplete string | Use an incremental/forgiving parser designed for partial JSON, or wait for the tool-call block to close before parsing at all |
| Instructor's retry loop is described in an interview or design doc as "constrained decoding" | Conflating the orchestration layer (retry-with-error-message) with the constraint layer (logit masking) | Name the actual mechanism: Instructor retries against a validated schema using the provider's native tool-calling/structured-output guarantee; it does not itself mask logits |
| Structured-output request is incompatible with citations or returns a 400 alongside another feature | Structured outputs (`output_config.format`) are documented as incompatible with citations and with message prefilling on at least one major provider | Check per-provider feature compatibility before combining structured output with other request-shaping features |

---

## Tradeoffs & when NOT to use it

- **Don't reach for constrained decoding as the default.** It is the strongest shape guarantee, but it requires self-hosted serving with logit access, adds infrastructure you may not otherwise need, and carries a documented reasoning-quality cost on tasks that need multi-step thought before answering. Start with tool-calling/structured-output on a hosted API; escalate to constrained decoding only when you have a specific, measured need for an absolute shape guarantee that the hosted path doesn't give you.
- **Don't force structure before reasoning completes on any reasoning-heavy task.** If the task genuinely requires chain-of-thought (multi-step math, causal analysis, anything where the final answer depends on intermediate derivation), constraining the entire generation from the first token is very likely to hurt accuracy regardless of which mechanism you use — the fix is architectural (reason first, constrain the extraction step second), not a config flag.
- **Don't treat schema validation as a correctness check.** A validator passing tells you the shape is right; it tells you nothing about whether the content is right. For high-stakes extraction (financial data, legal party assignment, medical values), budget for a separate semantic-correctness layer and don't let "it validated" become the last word.
- **Don't use full JSON mode ("just make it valid JSON with no schema") when you actually have a schema.** Legacy JSON-mode-without-a-schema guarantees syntactic validity only, not adherence to any particular shape, and is strictly weaker than a schema-backed structured-output or strict tool-use call at essentially the same cost; there's rarely a reason to choose it over the schema-backed version once a schema exists.
- **Streaming structured output for a UI that doesn't actually benefit from field-by-field reveal is unnecessary complexity.** If the client only uses the completed object anyway, wait for the block to close and parse once; building an incremental JSON parser for a UI that renders the whole object at once is effort spent on a problem you don't have.

---

## Interview questions

### Q1 — Name the three mechanisms for getting structured output from an LLM and rank them by guarantee strength.
**Testing:** baseline vocabulary and whether the candidate distinguishes mechanism from marketing term.
**Answer:** Prompting-and-hoping (weakest — no guarantee, needs a repair loop as core design), tool/function-calling schemas (strong — the model populates a validated API-level argument, reported failure rates under 0.1% on strict modes), and constrained decoding (strongest on shape — logits are masked at every token so invalid tokens have zero probability of being sampled, a hard guarantee rather than a cooperation contract).
**Follow-up trap:** *"Does the strongest guarantee mean you should always use it?"* — no. Constrained decoding's absolute shape guarantee comes with a documented cost to reasoning quality (10-30% degradation on some tasks per Tam et al. 2024) and requires self-hosted serving with logit access. The right mechanism is the weakest one that meets your actual reliability bar, not reflexively the strongest.

### Q2 — Explain, mechanically, how constrained decoding guarantees valid output.
**Answer:** The schema is compiled into a grammar — a finite-state machine for regular/JSON-schema-shaped constraints, a pushdown automaton for context-free grammars. At every decoding step, the decoder computes which tokens are valid continuations given the grammar's current state and the partial output so far, and masks every other token's logit to negative infinity before sampling. An invalid token isn't discouraged by a penalty; it has exactly zero probability after the softmax, so it literally cannot be sampled.
**Follow-up trap:** *"Why does this need model-hosting access, not just an API call?"* — because it operates on raw logits before sampling, which hosted chat-completion APIs don't expose to the caller. This is why constrained decoding lives in self-hosted serving stacks (vLLM, SGLang) with libraries like Outlines or XGrammar, not as something you can bolt onto a call to a provider's hosted endpoint.

### Q3 — Why can constrained decoding degrade content quality even while guaranteeing shape? This is the senior question in this whole topic.
**Testing:** whether the candidate has internalized the finding, not just heard of it.
**Answer:** Two mechanisms. First, prompt-level: if the schema forces an answer field before the model has finished reasoning, the model is grammatically required to start emitting the answer at the point the grammar demands it, whether or not the underlying reasoning is complete — this is the dominant effect. Second, decoder-level and more minor: masking high-probability tokens the model actually "wanted" forces a renormalization of the remaining valid tokens, which can amplify relative differences and shift the effective sampling distribution away from what the model would have produced unconstrained. Tam et al. (2024) measured 10-30% degradation on reasoning tasks from strict format constraints.
**Follow-up trap:** *"How do you mitigate this without giving up the shape guarantee?"* — don't constrain the entire generation from token one. Let the model reason freely (prose or a thinking block) first, then constrain only the final extraction step, or design the schema so free-form reasoning fields precede the structured answer fields. This targets the dominant, prompt-level cause directly rather than accepting the tradeoff or abandoning constrained decoding.

### Q4 — A contract-extraction pipeline populates `{"party_a": ..., "party_b": ...}` from a document, using strict tool-use validation. Every field validates. The two parties are swapped. What failed, and whose job was it to catch it?
**Answer:** Nothing "failed" in the schema-validation sense — the object is correctly shaped, every field is present and correctly typed, `additionalProperties` is satisfied. The failure is semantic: the model assigned the wrong entity's content to each field, and no mechanism in JSON Schema, strict tool use, or constrained decoding checks content meaning, only structure. Catching this requires a separate semantic-validation layer — a cross-check model call, a deterministic rule against a known value, or a downstream human review — that nobody gets for free just because validation passed.
**Follow-up trap:** *"Isn't this just a model-accuracy problem, unrelated to structured output?"* — the trap is agreeing too readily. It's specifically relevant to structured output because the shape guarantee creates false confidence: a team that sees "100% schema validation pass rate" in their metrics can reasonably but wrongly conclude the extraction is reliable, when validation pass rate says nothing about semantic correctness. Naming that gap explicitly is the point of the question.

### Q5 — Design a repair loop for a structured-extraction call. When do you retry, when do you reprompt, and when do you fail?
**Answer:** A three-rung escalation. Retry (resend as-is, possibly at different sampling) for a bare parse failure — malformed JSON is often a one-off sampling artifact rather than a systemic misunderstanding, so a fresh attempt is cheap and often sufficient. Reprompt (include the specific validation error in the next request) for a schema-validation failure — the model needs the new information about exactly what it got wrong, which the original prompt and schema alone didn't convey. Fail, after 2-3 reprompt attempts, with a structured error surfaced to the caller — an unbounded loop against a model that's confidently, consistently wrong about a field is a cost and latency sink with no exit condition and no reason to believe attempt 5 succeeds where attempts 1-4 didn't.
**Follow-up trap:** *"Instructor handles this automatically — so why would you ever build it yourself?"* — Instructor's default loop is a reasonable general-purpose implementation, but the escalation boundaries (how many retries, what counts as "fail," whether to alert a human) are policy decisions specific to your reliability and cost requirements, and the library's defaults may not match them. Understanding what the library is doing under the hood is what lets you tune those boundaries correctly rather than accepting defaults that either give up too early or loop too long.

### Q6 — What does the Instructor library actually do, and what does it not do?
**Answer:** It wraps a provider's API client, converts a Pydantic model into the provider's schema format (a tool schema, or a structured-output config), validates the response against that Pydantic model, and on validation failure retries with the validation error appended to the conversation so the model can self-correct — an orchestration and retry layer. It does not itself constrain generation at the token level; the actual shape guarantee still comes from whatever the underlying provider API's tool-calling or structured-output mode provides. Calling Instructor "constrained decoding" is a category error.
**Follow-up trap:** *"If Instructor doesn't constrain decoding, why does it still meaningfully reduce failures?"* — because most real-world structured-output failures are validation failures the model can fix given the specific error (wrong type, missing field, extra field), not failures that require a hard sampling-level constraint to prevent. The retry-with-error-message loop closes most of the practical gap between "the provider validated the shape" and "the content is exactly what you need," without needing logit-level access at all.

### Q7 — Which JSON Schema features are commonly unsupported by hosted structured-output APIs, and why does this matter operationally?
**Answer:** Recursive schemas, numerical constraints (`minimum`, `maximum`, `multipleOf`), string-length constraints (`minLength`, `maxLength`), and `additionalProperties` set to anything other than `false`. It matters because some SDKs quietly strip these from the schema sent to the model and validate them client-side after generation instead — which means a constraint you believe is a hard, decode-time guarantee may actually be a post-hoc check that runs after the (potentially non-compliant) generation already happened, changing your failure-handling story from "impossible" to "detected after the fact."
**Follow-up trap:** *"Your schema has a maxLength: 50 on a field. In production, you occasionally see fields longer than 50 characters slip through. Why?"* — `maxLength` is a string-constraint category that's commonly not enforced at generation time; if the SDK is silently stripping it and validating client-side, a bug in that client-side validation path (or an SDK version that doesn't implement the check at all) lets non-compliant output through with no generation-time protection to fall back on.

### Q8 — When would you deliberately NOT use structured output at all?
**Testing:** the real "when not to" for this topic.
**Answer:** When the task is genuinely open-ended and forcing any schema early would suppress the exploratory reasoning the task needs — brainstorming, open-form creative writing, or a first-pass analysis where you don't yet know the right shape for the answer. Also when the output is naturally prose that a human reads directly, where imposing structure adds translation overhead (schema definition, validation, potential quality cost) with no consumer that benefits from it. And specifically, don't force full-generation constrained decoding on any task requiring multi-step reasoning before the answer is known — the quality cost there is real and measured, not hypothetical.
**Follow-up trap:** *"Your team wants to add a JSON schema to every LLM call 'for consistency.' What's your pushback?"* — consistency of interface isn't free; it's justified when a downstream system actually parses and acts on the structured output programmatically. If the consumer is a human reading a summary, structuring it for machine-parseability adds constraint (and, if using constrained decoding, a measured quality cost) to solve a problem that doesn't exist for that consumer. Apply structure where something downstream needs to parse it, not reflexively everywhere.

### Q9 — Streaming a structured tool call: the client receives `{"name": "Al` mid-stream. How do you handle it?
**Answer:** Two viable approaches, chosen by whether the UI benefits from incremental reveal. First: use an incremental/forgiving JSON parser built for exactly this — one that reports which fields are fully resolved so far in a valid prefix, rather than repeatedly feeding a strict parser an incomplete string and catching exceptions. Second, simpler: treat the `input_json_delta` stream as opaque and only parse once the tool-call content block closes (`content_block_stop`), trading incremental UI updates for implementation simplicity. Most production systems default to the second unless there's a specific UX reason (e.g., showing extracted fields populate live) to build the first.
**Follow-up trap:** *"Your incremental parser occasionally reports a field as resolved, then the final complete parse shows a different value for that field. How?"* — the model can still emit output after that field syntactically closes if the schema allows revision within the same object (rare but possible depending on schema shape), or, more commonly, the "resolved" report from a forgiving parser is a best-effort read of a valid JSON prefix, not a guarantee that value is final — a partial numeric literal like `4` could still become `42` on the next token. Incremental parsers should surface partial values as provisional, not committed, until the block actually closes.

### Q10 — Compare OpenAI's Structured Outputs and Anthropic's approach to structured output.
**Answer:** OpenAI's Structured Outputs constrains the response format directly with `strict: true` and `additionalProperties: false`, reporting failure rates below 0.1% and treating this as the primary "JSON mode" successor. Anthropic's primary documented mechanism is tool use, with `strict: true` on the tool definition delivering a comparable reliability guarantee through the tool-calling path rather than a separate top-level JSON-response-format flag, alongside a newer `output_config.format` / `client.messages.parse()` path for response-level structured output when the answer isn't naturally a tool argument. Both share largely the same JSON Schema subset support and limitations.
**Follow-up trap:** *"So they're functionally interchangeable — does the distinction matter for how you design a multi-provider pipeline?"* — it matters for portability: code written against one provider's top-level JSON-schema response format doesn't translate directly to the other's tool-calling-centric approach without an abstraction layer, which is exactly the gap libraries like Instructor exist to paper over by normalizing "give me this Pydantic model back" across providers regardless of which underlying mechanism each one uses.

---

## Red flags that fail you

- Saying "just use JSON mode" with no distinction from schema-backed structured output or tool use.
- Not knowing that constrained decoding operates on raw logits and requires self-hosted serving.
- Treating a passing schema validation as proof the content is correct.
- Calling Instructor's retry loop "constrained decoding."
- No awareness that forcing structure can degrade reasoning-heavy task performance.
- Building an unbounded reprompt loop with no fail condition.
- Assuming every JSON Schema keyword is enforced at generation time by every provider.
- No answer for the semantic-correctness gap when asked directly.

---

## Cheat card

```
THREE MECHANISMS (increasing guarantee strength)
  1. prompt-and-hope    : no guarantee; repair loop is CORE design, not fallback
  2. tool/function schema: model call, sensor by API; <0.1% failure reported
                            (OpenAI strict); Anthropic: strict:true on tool def,
                            or output_config.format / messages.parse()
  3. constrained decoding: logits MASKED at every token -> invalid = impossible
                            (not discouraged, IMPOSSIBLE). Needs raw logit access
                            -> self-hosted serving (vLLM/SGLang), Outlines/XGrammar

WHY CONSTRAINED DECODING CAN HURT QUALITY (senior insight)
  Tam et al. 2024 (EMNLP, arXiv:2408.02442): 10-30% reasoning degradation
  1. prompt-level (DOMINANT): schema forces answer field before reasoning done
  2. decoder-level (minor): masking + renormalization distorts distribution
  FIX: reason unconstrained first (prose/thinking), constrain ONLY final
       extraction; put free-form fields BEFORE structured answer fields

JSON SCHEMA SUPPORT (hosted APIs)
  YES: basic types, enum, const, anyOf, allOf, $ref/$def, string formats
  NO (often silently stripped + validated client-side after gen):
       recursive schemas, min/max/multipleOf, minLength/maxLength,
       additionalProperties != false

THE UNSOLVED PROBLEM: semantics, not shape
  swapped fields (party_a/party_b, billing/shipping) pass EVERY validator
  fix: separate semantic-validation layer, never "it validated" = correct

REPAIR LOOP LADDER
  parse failure       -> RETRY (often a sampling artifact)
  validation failure   -> REPROMPT (include the specific error -> new info)
  2-3 reprompts failed -> FAIL loudly, structured error, don't loop forever

LAYER RESPONSIBILITIES (don't conflate)
  Pydantic   = spec + validation (pure Python, no model call)
  Instructor = orchestration: call -> validate -> reprompt-on-error loop
  Outlines/XGrammar = the actual CONSTRAINT (logit masking at decode time)

WHEN NOT TO USE STRUCTURED OUTPUT
  open-ended exploratory tasks where early schema suppresses useful reasoning
  prose consumed directly by a human, no downstream parser
  reasoning-heavy tasks: never force full-generation constrained decoding
```

## Sources

- ["Let Me Speak Freely? A Study on the Impact of Format Restrictions on Performance of Large Language Models" (Tam et al., EMNLP 2024 Industry Track)](https://arxiv.org/abs/2408.02442) — 10-30% reasoning degradation from format constraints — accessed 2026-08-01
- [Structured Decoding in vLLM: a gentle introduction](https://blog.vllm.ai/2025/01/14/struct-decode-intro.html) — token-bitmask mechanism — accessed 2026-08-01
- [XGrammar-2: Efficient Dynamic Structured Generation Engine for Agentic LLMs](https://arxiv.org/pdf/2601.04426) — vocabulary partitioning for fast mask construction — accessed 2026-08-01
- [Instructor — Multi-Language Library for Structured LLM Outputs](https://python.useinstructor.com/) — Pydantic wrapping, validate-and-retry loop — accessed 2026-08-01
- [Claude API — Structured Outputs (tool use, strict mode, `output_config.format`)](https://platform.claude.com/docs/en/build-with-claude/structured-outputs) — accessed 2026-08-01
- [JSONSchemaBench: A Rigorous Benchmark of Structured Outputs for Language Models (arXiv:2501.10868)](https://arxiv.org/pdf/2501.10868) — cross-provider structured-output reliability comparison — accessed 2026-08-01

## Changelog
- 2026-08-01 — created
