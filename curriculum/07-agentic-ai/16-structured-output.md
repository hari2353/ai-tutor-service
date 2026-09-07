# Structured Output: JSON Schema, Constrained Decoding, Repair Loops

> **Track:** T07 Agentic AI · **Time:** 2h · **Prereqs:** `T07-tool-engineering` · **Updated:** 2026-09-06
> **Module id:** `T07-structured-output` · **Tags:** production, critical

## The 30-second version

Structured output is the discipline of making an LLM's emission consumable by code with a guarantee attached, and there are exactly three mechanisms, used stacked rather than as alternatives: **prompt-and-validate** (ask for JSON, parse with pydantic, accept first-shot validity somewhere between 0% on naive small models and high-90s on trained large ones), **constrained decoding** (compile the JSON Schema into a grammar and mask logits at every sampling step so invalid output is structurally impossible — OpenAI's Structured Outputs, launched 2024-08-06, took gpt-4o from 93% trained-only to a claimed 100% schema adherence on their evals, versus under 40% for gpt-4-0613 by prompting alone), and the **repair loop** (validation error fed back as an actionable message, bounded retries, then field-level salvage) as the backstop that never goes away. Constrain the machine-facing fields; keep human-facing prose free; validate even under constrained decoding, because refusal, truncation at `max_tokens`, and provider subset limits all void the guarantee. The senior-level caveat is that strictness costs quality: format restrictions measurably degrade reasoning, and the largest share of that format tax comes from the request in the prompt rather than the mask at the decoder — so measure the accuracy delta before shipping strict mode, and put reasoning in a free-form field inside the schema instead of constraining the model's thinking.

## Why this gets asked

Because every agent is a compiler with a non-deterministic front-end. Tool arguments, graph-state updates, router decisions, structured handoffs between subagents, the final response your UI renders — all of it is LLM output fed into `json.loads` or a pydantic model, and the model's native output is prose. Free-text parsing is the single most fragile seam in a production agent: nothing in your code changes, the provider updates a model snapshot, and suddenly the model wraps JSON in markdown fences, changes its quoting style, or stops emitting a field it used to always emit — and `json.loads` starts throwing at step 7 of a 9-step run, discarding the run in front of the user.

The interviewer has personally lived one of three incidents. The 3am page where the only thing that changed was a model version and the fix was a prompt tweak. The cost incident where retry-on-parse-failure with no retry cap turned a bad model day into a 40x bill. Or the quiet one: constrained decoding was enabled, validity hit 100%, and accuracy went *down* — and the candidate who has never seen the format tax will insist that is impossible.

The question probes in layers. A junior candidate knows JSON mode exists. A mid-level candidate knows JSON mode guarantees nothing about your schema. A senior candidate knows the supported-subset limits, the refusal and truncation holes in the 100% claim, and the measured accuracy cost of strictness. A principal can say when NOT to constrain, how to version a schema against model updates, and how to evaluate structured output quality rather than just validity. This module is the difference between those layers.

---

## Lineage: past → present → future

**What came before.** 2022 to early 2024 was regex, `JSON.parse`, and prayer. ReAct (Yao et al., 2022) emitted `Action: search[query]` as prose and you regexed it out — the tool-engineering module covers how badly that went. The academic root of the fix is older than people expect: PICARD (Scholak et al., 2021) constrained GPT-2 code generation with a parser, masking tokens that would make the prefix unparseable. Willard & Louf's Outlines (Oct 2023) made this practical at scale — compile a regex or JSON Schema into a finite-state machine, precompute per-state token masks, and apply them as a logit bias at every decoding step. jsonformer (2023) took the opposite approach: fill in the schema skeleton yourself and only let the model generate the value spans. guidance, lm-format-enforcer, and Zod-based re-asking followed. OpenAI's JSON mode (DevDay, Nov 2023) was the productized admission that parsing free text was not working — and the specific pain that killed the era is worth naming: **JSON mode guaranteed valid JSON and nothing else.** Syntactically perfect JSON with missing required fields, wrong types, and hallucinated enum values still exploded your validators; the model happily wrapped objects in prose or fenced them in markdown; and a provider-side model update silently changed output shape overnight, so your code that never changed broke in production. Validation-after-the-fact plus unbounded retries was the default posture, and unbounded retries are a cost bomb, not a reliability strategy.

**Where it stands now.** Constrained decoding is productized everywhere. **OpenAI Structured Outputs** (Aug 6, 2024) ships in two forms — `strict: true` on function/tool definitions, and `response_format: json_schema` — and works by converting the schema to a context-free grammar, pre-processing it once (first request with a new schema takes extra latency: under 10 seconds typically, up to a minute for complex schemas, cached after), then masking the next-token distribution at every step. Their numbers: gpt-4o-2024-08-06 scores 100% on their complex JSON Schema evals with Structured Outputs, 93% trained-only without the mask, versus under 40% for gpt-4-0613. **Anthropic** GA'd the equivalent out of the `structured-outputs-2025-11-13` beta: JSON outputs via `output_config.format` and strict tool use via `strict: true`, with a documented subset — all basic types, scalar enums, `const`, `anyOf`/`allOf` (with limits), `$ref`/`$defs`, `required` plus `additionalProperties: false`, ten string formats (date-time, time, date, duration, email, hostname, uri, ipv4, ipv6, uuid), and `minItems` of only 0 or 1 — while recursive schemas, numeric ranges (`minimum`/`maximum`/`multipleOf`), string lengths (`minLength`/`maxLength`), external `$ref`s, and regex backreferences/lookarounds are **not** supported and produce a 400 at request time rather than being silently ignored. Open serving stacks fused grammar engines: vLLM renamed its `guided_json`/`guided_regex`/`guided_choice`/`guided_grammar` parameters to `structured_outputs` (v0.12.0 removed the old names), with xgrammar — integrated Dec 2024 — as the flagship backend and guidance/llguidance as the alternative; XGrammar also shipped into SGLang (Nov 2024), TensorRT-LLM (Jan 2025), Modular MAX (Feb 2025), OpenVINO GenAI (Sep 2025), and Mirai (Dec 2025), with XGrammar-2 (May 2026) targeting dynamic agentic schemas. The **instructor** library productizes the repair loop across every provider with `response_model` and `max_retries=3`. **The live disagreements are real.** First, *quality versus strictness*: "Let Me Speak Freely?" (Tam et al., 2024) measured significant reasoning degradation under format restrictions, with stricter formats degrading more — JSON, whose every bracket must close, forces structural commitments before reasoning completes — and *The Format Tax* (2026) localized most of the loss to the format-requesting instructions in the prompt rather than the decoder mask, finding recent closed-weight models pay little or no tax while open-weight models still do; the One-Word Census follow-up (2026) showed that merely *requesting* JSON collapses answer diversity (modal answer share 41% → 64%, distinct answers 52 → 36) and that decoder enforcement adds almost nothing further (-0.03 bits). Second, *the overhead story*: XGrammar's claim of near-zero JSON overhead (over 99% of the token mask precomputable at compile time, 3.5x faster masking on JSON schemas and 10x on general CFGs, 14x/80x end-to-end versus earlier engines on Llama-3-8B/H100) coexists with When Correct Isn't Usable (2026) measuring 3.6x–8.2x latency overhead for constrained decoding on 7–9B models, PSC (2026) showing mask computation scaling linearly with vocabulary size, and the trie-automaton work measuring vLLM+XGrammar at 7.5 req/s versus 219 req/s with precomputed masks over large finite sets at batch 256 — a 29x gap they name the cardinality wall. Both sides are right because overhead is a function of schema class (flat extraction schemas ≈ free; multi-thousand-value enums and deep recursion ≈ not) and batch size (CPU-side mask computation becomes the bottleneck exactly when GPU throughput is highest). Third, *constrained decoding versus learned structure*: SLOT (2025) fine-tuned Mistral-7B *with* constrained decoding to 99.5% schema accuracy and 94% content similarity, beating Claude 3.5 Sonnet by +25/+20 points — a small model plus enforcement beats a large model asked nicely.

**Where it's heading.** High confidence: **structured output becomes the default agent interface, and the grammar compiler is a fused part of the serving stack.** You cannot ship a serious inference engine in 2026 without one; the remaining work is performance and coverage, not adoption. High confidence: **mask computation keeps getting specialized** because it is the CPU bottleneck that faster GPUs keep exposing — PSC's parser-stack classification makes masking independent of vocabulary size (up to 700x faster on programming grammars, 30x on schema-conformant JSON), trie automata exploit finite-set structure for sub-100ms compilation at 10,000 values, and XGrammar-2 targets the dynamic schemas agents generate per call. Medium confidence: **schema design becomes instruction engineering** — the schema-key-wording study (2026) demonstrated that key names are an instruction channel that measurably moves accuracy while prompts stay fixed, with model-dependent effects (Qwen models follow schema keys more, Llama models follow prompt text more), which will push schema authoring from "draw the shapes" toward measured, per-model prompt work. Medium confidence: **the repair loop moves inside decoding** — ATLAS-RTC (2026) detects drift from the output contract mid-generation and applies biasing, masking, or rollback, improving first-attempt success by 20 to 37.8 percentage points with up to 88% latency reduction in failure-dominated settings; expect token-level runtime control to be productized. Speculative but security-critical: **schemas become a recognized attack surface.** Constrained Decoding Attacks (CDA, CCS 2026) hide jailbreak payloads in grammar-enforced fields — DictAttack decouples payload across prompt and dictionary grammar, achieving 94.3–99.5% attack success on flagship models and still 75.8% against state-of-the-art jailbreak guardrails. If you accept user-supplied schemas, expect schema auditing to become a mandatory review step, the way SQL review already is. And one wildcard for diffusion LLMs: parallel block generation breaks sequential masking entirely, and DINGO (2025) is the first provably distribution-preserving constrained decoding for them.

---

## Mental model

**Structured output is a rail yard: the grammar is the track, the model is the train, and the schema says which siding the cargo goes to.** The track makes derailment impossible. It does not tell the engineer what cargo to load, and it does not prevent the train from arriving at the wrong siding with the wrong freight. Syntax is the track; semantics is the freight.

```
        ┌───────────────────────  THE RELIABILITY PIPELINE  ───────────────────────┐
        │                                                                          │
 prompt ─→ sampler ─→ [ LOGIT MASK ] ─→ text ─→ validate ──pass──→ typed object   │
 (+schema,           vocab ≈ 128K       invalid       (pydantic)                    │
  +examples)         tokens checked     tokens get                │                │
                     per step           p = 0                     │ fail           │
                     (grammar/CFG)                                 ↓                │
        │                                        ┌── repair loop ──────────┐      │
        │                                        │ error msg fed back      │      │
        │                                        │ retry ≤ 3, escalate    │      │
        │                                        │ salvage fields → queue │      │
        │                                        └─────────────────────────┘      │
        └──────────────────────────────────────────────────────────────────────────┘

 THREE HOLES IN EVERY GUARANTEE (why the validator never goes away):
   1. REFUSAL     safety refusal bypasses the grammar by design → 200, billed, schema broken
   2. TRUNCATION  max_tokens cut mid-array → invalid JSON, finish_reason = "length"
   3. SUBSET      providers enforce a subset of JSON Schema → unsupported keyword = 400,
                  or your SDK silently strips it and you never notice
```

The one-line takeaway for an interview: **the mask makes invalid output impossible; it makes wrong output just as possible as before.** Everything else in this module is about the second half of that sentence.

---

## How it actually works

### 1. JSON Schema for LLMs: what a grammar can honor and what it can never enforce

A JSON Schema compiles into a grammar because the schema's structural claims — "this is an object with these keys, this value is one of these three strings, this array holds items of that shape" — are all expressible as a set of production rules. What the compiler can honor:

- **Types**: `string`, `integer`, `number`, `boolean`, `null`, `object`, `array` — each maps to a token-level automaton.
- **`required` and key sets**: the mask can force `{"name"` to appear after `{` and can forbid any key not in `properties` when `additionalProperties: false`.
- **Enums of scalars**: at an enum position, only the tokens of the allowed values pass the mask. This is the highest-value constraint per token — it converts a whole class of typos and hallucinations into structural impossibilities.
- **String formats and regex**: a format like `uuid` or a simple `pattern` compiles to a small automaton over characters. Supported with sharp edges: Anthropic supports ten formats but rejects backreferences, lookahead/lookbehind, and `\b` in patterns; complex `{n,m}` quantifiers can 400.
- **Nesting, `anyOf`, `$ref`**: recursion depth is where FSM-based engines die and CFG/PDA-based engines (OpenAI's choice, XGrammar's choice) earn their keep — an FSM cannot match parentheses at arbitrary depth, which is why OpenAI explicitly cites recursive schemas like a UI component tree (`children: { "items": { "$ref": "#" } }`) as the case a regex-compiler cannot express. Anthropic, notably, still does not support recursive schemas at all — the subsets differ per provider, which is itself a portability hazard.

What no grammar can enforce, ever:

- **Semantic correctness of values.** The mask guarantees `status` is one of `"pending" | "shipped" | "delivered"`; it cannot guarantee the model picked the right one for this ticket. A schema-conformant wrong answer is worse than a parse error, because your validation layer will pass it.
- **Cross-field constraints.** "If `other_reason` is selected, `explanation` must be non-empty" is a semantic dependency between positions; grammars are positional, not relational. Enforce in code (pydantic model validators) and let the repair loop handle violations.
- **Anything outside the supported subset.** `minimum`/`maximum`/`multipleOf`, `minLength`/`maxLength`, `patternProperties`, `uniqueItems` — either the provider 400s at request time (Anthropic's documented behavior, the honest failure) or your SDK silently strips the constraint into a description string (the Anthropic and OpenAI Python/TypeScript SDKs both do schema transformation: remove unsupported keywords, append them to field descriptions) and you discover at 2am that `age` was never range-checked. A third-party schema fed to a provider that accepts the keywords but ignores them is the silent-worst case. **Contract-test your schema against the actual provider subset in CI**, the same way you would test an API client against a real server.

One subtlety that matters for design: **Anthropic reorders properties** — required properties come first in schema order, then optionals — so if output ordering matters to a downstream parser, mark everything required or parse order-free.

### 2. Constrained decoding: how the mask is actually computed, and what it costs

The mechanism, one level down:

1. **Compile (once per schema)**: JSON Schema → CFG → pushdown automaton (PDA). Because a tokenizer's 128,000-token vocabulary does not align with grammar terminals — `true` might be one token, `":` another, and a single token can span a grammar boundary — the compiler computes, for every automaton state, which tokens keep the prefix inside the language. XGrammar's core insight is that **over 99% of tokens are context-independent** — their validity depends only on the current automaton position, not the PDA stack — so they are precomputed into an adaptive token mask cache at compile time; the remaining context-dependent tokens are checked at runtime against a persistent tree-structured execution stack.
2. **Mask (every step)**: after each sampled token, advance the automaton, fetch the cached valid-token set plus the runtime-checked remainder, apply a -inf mask to every other logit, then softmax. Invalid tokens get probability exactly 0; the renormalization transfers their mass to the valid set.
3. **Overlap (serving stacks)**: XGrammar co-designs with the inference engine to overlap grammar processing on the CPU with GPU compute, plus jump-forward decoding (skip over tokens the grammar fully determines) and rollback APIs for speculative decoding.

**The overhead story, honestly told with numbers.** Naive constrained decoding checks every vocabulary token at every step: with a ~128K vocabulary (Llama-3 class) and a mask check even at ~5.8μs per step, CPU-side masking becomes the bottleneck precisely in large-batch serving where GPU throughput is highest. The measured landscape:

| Measurement | Number | Source |
|---|---|---|
| XGrammar masking speedup vs prior engines (JSON Schema / general CFG) | up to 3.5x / 10x | XGrammar benchmarks (Llama-3-8B) |
| End-to-end engine speedup (JSON Schema / CFG, H100, batched) | up to 14x / 80x | XGrammar benchmarks |
| Masking overhead measured on 7–9B models, some settings | 3.6x–8.2x latency | When Correct Isn't Usable (2026) |
| Per-step mask compute vs XGrammar, large finite sets (trie automata) | 0.65μs vs 5.8μs (7x) | Trie Automata paper (2026) |
| vLLM throughput, batch 256, 10K-value choice sets | 7.5 req/s (XGrammar path) vs 219 req/s (precomputed trie masks) — 29x | Trie Automata paper (2026) |
| Vocab-independent masking (PSC) | up to 30x faster for schema-conformant JSON, 700x for programming grammars | PSC (2026) |
| First-request schema preprocessing | <10s typical, up to 60s complex, then cached | OpenAI launch documentation |

The reconciliation is the senior answer: **flat extraction schemas on a compiled-and-cached engine are effectively free; huge enums, deep recursion, cold schemas on a latency SLO, and very large batch sizes are not.** Measure on your schema class, not on the vendor's.

**The quality cost — the trap the whole industry fell into.** "Let Me Speak Freely?" (2024) found format restrictions significantly degrade reasoning, and *stricter* formats degrade it *more*; JSON is the worst common offender because closed brackets force the model to commit to structure before it has finished deciding the content. The Format Tax (2026) sharpened the diagnosis: sampling distortion from the mask is only a fraction of the loss — **the dominant cost is the format-requesting instructions in the prompt**, applied before any decoder constraint; recent closed-weight models show little to no tax (it is a training artifact, not a law of nature), while open-weight models still pay it; and decoupling reasoning from formatting — freeform first, reformat in a second pass — recovers most of the loss. The diversity-collapse result (2026) adds the kicker: just asking for JSON changes *which answer* the model picks (modal answer share 41% → 64%, distinct answers 52 → 36), and enforcing the schema at the decoder compresses diversity no further than the request did (-0.03 bits). Practical consequence, in priority order: keep an unconstrained reasoning channel (a free-text `reasoning` field inside the schema, or a two-pass generate-then-reformat pipeline); constrain only the machine-facing fields; and A/B the constrained and unconstrained versions on your own eval, because your model's tax is your model's tax.

### 3. Repair loops: the economics of "try again"

The repair loop is the oldest mechanism and the one you keep even after adopting constrained decoding, because it is the only one that handles semantic violations (cross-field rules, value quality, anything code-validated):

```
validate → serialize errors → feed back → retry → [≤3] → salvage → human queue
```

Four design decisions determine whether the loop is an asset or a cost bomb:

1. **Bounded retries.** Cap at 3 (instructor's default is `max_retries=3`). Unbounded retry loops are the classic incident: a model update pushes first-shot validity down, every request starts paying 2–4x inference cost, and nobody notices until the bill arrives. A retry is a full inference pass — same input tokens re-processed, new output tokens paid for.
2. **Error messages that teach.** Pydantic's `ValidationError` gives you `loc` (the field path), `msg`, and `type` per error. "Invalid JSON" teaches nothing; `customer_id: Input should be a string prefixed 'cus_' — you returned an integer` names the fix. This is the errors-as-observations principle from `T07-tool-engineering` §6, applied to your own output contract: the error text is a prompt.
3. **Change something between retries.** At low temperature a model re-asked identically can reproduce a near-identical failure — the same-error thrash loop. The repair attempt must differ: the validation feedback itself is usually enough; escalating temperature or adding a concrete example is the second lever.
4. **A salvage path.** After the budget is spent, do not return a parse error to the caller: extract what you can field-by-field from the last raw text (regex/scan per field against the schema), fill the rest with nulls or defaults, flag the record `needs_review: true`, and queue it for a human or a stronger model. A degraded-but-usable record beats a 500.

The loop's metrics are its health check: first-attempt validity rate, retry-rate distribution (a healthy system is ~90%+ first-shot with modern models and a good prompt), and same-error-thrash count (evidence your feedback is not landing).

### 4. Function calling as the productized form

Strict function calling is the same grammar machinery applied to tool arguments rather than the whole response: `strict: true` on a tool definition (OpenAI) or strict tool use (Anthropic) constrains the argument stream to the tool's input schema — and, in Anthropic's case, to the tool name as well. Three provider facts worth knowing cold: OpenAI's strict mode is **incompatible with parallel function calls** (`parallel_tool_calls: false` required, from the launch documentation); OpenAI's Structured Outputs requests are **not Zero Data Retention eligible**, which matters the moment a compliance team asks; and Anthropic's strict tool use and JSON outputs share the same subset limitations, so the 400-on-unsupported behavior applies to your tool schemas too. The strategic reading: tool calling won as the interface not because it is a better idea but because it is constrained decoding with the schema pre-validated at registration time instead of per request — which is also why malformed tool calls went from a daily debugging event to a non-event everywhere it was adopted.

---

## Build it from scratch

The repair loop, minimal and honest. This is the mechanism under instructor and under every serious production wrapper; the value of writing it once is that you stop treating validation feedback as a black box.

```python
# untested sketch — pydantic v2; pattern is battle-tested, this exact file is not
import json, re
from pydantic import BaseModel, ValidationError

MAX_RETRIES = 3

def structured_call(client, model: str, messages: list[dict],
                    schema: type[BaseModel], **kw) -> BaseModel | None:
    """Prompt-and-validate with bounded repair. Returns None only if salvage fails."""
    sys = [{"role": "system", "content":
            f"Output ONLY JSON matching this schema. No prose, no markdown fences.\n"
            f"{json.dumps(schema.model_json_schema())}"}]
    history, text = list(messages), ""
    for attempt in range(MAX_RETRIES + 1):
        raw = client.chat.completions.create(model=model, messages=sys + history, **kw)
        text = raw.choices[0].message.content or ""
        if raw.choices[0].finish_reason == "length":          # truncation hole
            kw["max_tokens"] = min(int(kw.get("max_tokens", 1024)) * 2, 8192)
            continue
        try:
            return schema.model_validate(json.loads(text))    # parse + validate
        except json.JSONDecodeError as e:
            fb = f"That was not valid JSON ({e.msg} at char {e.pos}). Output corrected JSON only."
        except ValidationError as e:
            fb = "Schema violations:\n" + "\n".join(
                f"- {'.'.join(map(str, er['loc'])) or '<root>'}: {er['msg']}"
                for er in e.errors()) + "\nOutput corrected JSON only."
        history += [{"role": "assistant", "content": text},
                    {"role": "user", "content": fb}]           # feedback TEACHES the fix
    return salvage(text, schema)

def salvage(text: str, schema: type[BaseModel]) -> BaseModel | None:
    """Field-level extraction from the last raw output. Last resort before a human."""
    fields = schema.model_json_schema().get("properties", {})
    found, ok = {}, True
    for name, spec in fields.items():
        m = re.search(rf'"{name}"\s*:\s*("[^"]*"|\d+|[a-z]+)', text or "")
        if m is None:
            found[name] = None; ok = False
        else:
            v = m.group(1)
            found[name] = json.loads(v) if spec.get("type") != "string" else v.strip('"')
    obj = schema.model_construct(**found)                     # skips validators by design
    return obj if ok else None                                # None → caller queues a human
```

What this sketch deliberately does not do: no constrained decoding (add `response_format` / `strict: true` when the provider supports it and you will delete most of the retry traffic); no patch-style re-asking (instructor's refinement only re-requests the failed fields, which is cheaper than a full re-ask on wide schemas); no cross-field validators (add pydantic `model_validator`s and the same feedback loop handles them). A matching lab would build this against a fault-injecting fake provider and measure first-attempt validity at each refinement; ask for `/tutor-lab structured-output` if you want it.

---

## How it's done in production

**OpenAI.** Two surfaces: `strict: true` on tool/function definitions (works on everything from gpt-4-0613 forward that supports tools) and `response_format: {type: "json_schema", strict: true}` (newer models; the Responses API equivalent is `text.format`). The SDK's `.parse()` helpers convert pydantic/Zod models to schemas and deserialize automatically, and surface a `refusal` field when the model refused instead of emitting schema-conformant output. Their own docs recommend Structured Outputs over JSON mode in every case where it is available. Numbers to quote: 100% adherence claim (scoped: supported subset, no refusal, not truncated), 93% trained-only, <40% gpt-4-0613, first-request compile <10s typical / up to 60s then cached, `parallel_tool_calls: false` required, ZDR-ineligible.

**Anthropic.** `output_config.format: {type: "json_schema", schema: ...}` for JSON outputs and `strict: true` on tools (both GA out of the `structured-outputs-2025-11-13` beta; the old `output_format` field still transits but the v1.0 Python SDK rejects it on the beta client). The subset is documented and enforced with a 400 — no `minimum`/`maximum`/`multipleOf`, no `minLength`/`maxLength`, no recursive schemas, no external `$ref`, `minItems` only 0 or 1, `additionalProperties` must be `false`, ten string formats supported, regex without backreferences/lookarounds/`\b`. Python/TypeScript/Ruby/PHP SDKs transform schemas automatically (strip unsupported keywords into field descriptions) — convenient, and a trap: your range constraint becomes prose. Property ordering: required first, then optional. On refusal you get a 200, you are billed, and the output violates your schema (`stop_reason: "refusal"`); on truncation, `stop_reason: "max_tokens"` — check both before parsing.

**vLLM and self-hosted stacks.** OpenAI-compatible server takes `structured_outputs` extras — `json` (JSON Schema or a pydantic-derived schema), `regex`, `choice`, `grammar` (EBNF), `structural_tag` — replacing the `guided_json` family removed in v0.12.0. Backends: `auto` picks per request; `xgrammar` and `guidance` are the named options (Outlines is the research ancestor and still a Rust-regex-compatible option in some stacks). Offline inference uses `StructuredOutputsParams(json=...)` inside `SamplingParams`. Reasoning models have a real gotcha: with a Qwen3-Coder-class model, structured outputs silently disable in reasoning mode unless you launch with `--structured-outputs-config.enable_in_reasoning=True` (v0.11.2+) — a symptom you will meet as "the grammar works on chat models and does nothing on the reasoning model."

**The instructor library.** The productized repair loop: `instructor.from_provider(...)` wraps any of a dozen provider clients, `response_model=YourPydanticModel`, automatic validation-retry with the error message appended (default `max_retries=3`), streaming partial objects, and patch-based re-asking modes. It is the right default for extraction-shaped work; use PydanticAI when the same typed workflow needs an agent runtime around it.

### What breaks at scale

| Symptom | Cause | Fix |
|---|---|---|
| p99 latency 10–60s on first request per schema | first-request grammar compilation, cold cache | warm known schemas on deploy (send one canary call); cache the compiled artifact; never introduce a brand-new schema on a latency-critical path untested |
| `400: unsupported schema feature` in prod | `minLength`/`minimum`/recursive schema/external `$ref` in the schema | subset-check schemas in CI against the target provider; let the SDK transform, but assert the transformed schema still carries your constraints somewhere |
| 100% valid JSON, but accuracy dropped after enabling strict mode | format tax: request + mask distort reasoning (measured; open-weight models pay most) | free-form `reasoning` field inside the schema, or two-pass freeform-then-reformat; A/B constrained vs unconstrained on your eval |
| Validity fine, values subtly wrong (`status` always `"pending"`) | grammar enforces membership, not choice; required-everything schemas force fabrication | enums only for closed vocabs; optional + explicit `null` over hallucinated defaults; `"other"` escape valve with free-text field |
| Throughput collapse at high batch with guided decoding on | CPU-side mask computation scales with vocab size and batch; cardinality wall on huge enum/choice sets | xgrammar/guidance backend, precompiled masks, trie-style masks for large finite sets, cap enum cardinality, shard hot grammars |
| `finish_reason: "length"`, JSON explodes mid-array | `max_tokens` truncation voids the guarantee; long arrays are the typical victim | budget output tokens per schema (count array items), cap array size in the schema, retry with continuation or larger `max_tokens` |
| 200 response, schema violated, no error | safety refusal path bypasses the grammar by design (OpenAI `refusal` field / Anthropic `stop_reason: "refusal"`); billed either way | check refusal/stop_reason before parsing; route refusals to a policy path, not a retry |
| Same validation error repeats 3x then fails | identical re-ask reproduces the failure; feedback not actionable | error text must name the field path and the fix; escalate temperature or add an example on retry 2 |
| Bill spiked 4x the day after a provider model update | unbounded or high retry cap on a validity regression | hard cap retries ≤3, alert on retry-rate and first-attempt-validity deltas, canary model updates |
| Markdown fences around the JSON (` ```json `) | JSON mode off / prompt conflict / model drift | strict response_format where available; strip fences before parsing as a repair; never regex-extract and hope |
| Field constraint silently not enforced | SDK stripped unsupported keyword into a description | contract-test: send the schema, verify the 400 (or the enforcement) for every constraint you rely on |
| Jailbreak payload executed via user-supplied schema | grammar fields are an injection channel (CDA: DictAttack 94.3–99.5% ASR, 75.8% even vs guardrails) | audit untrusted schemas like SQL: allowlist keywords, cap enum cardinality and pattern complexity, cap compile time; do not let user schemas reach the engine raw |

Instrument per schema, not just per endpoint: first-attempt validity, retry-rate distribution, refusal rate, truncation rate, per-field error frequency (the field that fails most is the field whose description is bad), and p50/p99 with a warm versus cold compile cache.

---

## Tradeoffs & when NOT to use it

- **Tiny fixed vocabulary: do not compile a grammar to pick one of three strings.** A sentiment label with 3 values needs a membership check, not a CFG. Prompt for the enum, parse with `in {"pos","neg","neutral"}`, fall through to the repair loop on the 1% miss. vLLM's `choice` parameter is exactly this optimized case — use it if you are already there; do not adopt a serving stack *for* it.
- **One-shot human-facing output: prose is the point.** Constraining a summary, an email, or an answer that a person reads buys you nothing and costs the format tax — and, per the diversity result, even the *request* narrows which answer you get. The one exception is the hybrid pattern: a thin envelope (`{"answer": string, "citations": [...]}`) where the prose lives unconstrained inside a field. That is the correct use, and it is different from constraining the prose itself.
- **Ultra-low-latency paths: read the compile and mask numbers before committing.** First request per schema is 10–60s slower; per-step masking is microseconds but multiplies by batch; 3.6x–8.2x overhead was *measured* on some model/schema classes. If you have a p95 budget measured in tens of milliseconds, warm the cache, cap schema complexity, and benchmark the actual schema — vendors' "near-zero" claims are scoped to flat JSON schemas, and the cardinality wall is real past a few hundred enum values.
- **Cross-field and value-level constraints: the grammar cannot help you.** `if status == "other"` semantics, range checks outside the subset, referential integrity — these belong to code validation plus the repair loop. Designing a schema hoping the grammar will enforce semantics is the category error; a grammar is positional, not relational.
- **Reasoning-heavy tasks with open-weight models: measure the tax first.** The Format Tax result is unambiguous for open-weight models: request + mask can cost real accuracy on math/logic-style tasks, and most of it is in the request. Two-pass (freeform, then a cheap reformat call with the strict schema) recovers most of it at the price of an extra inference pass — often cheaper than the accuracy you lost, sometimes not. Decide by eval, per model: recent closed-weight models measured near tax-free.
- **Untrusted schemas are a security decision, not a feature flag.** If your product accepts customer-uploaded schemas, you own CDA-class risk: enum and dictionary fields can carry jailbreak payloads that the grammar *enforces* into the output, with measured 94–99.5% success against flagship models and 75.8% even with jailbreak guardrails running. Audit, allowlist, and cap — the same review you give customer SQL.
- **Do not let strictness substitute for design.** An over-strict schema (everything required, enums for open concepts, no nulls) produces 100%-valid garbage: hallucinated values forced by the mask. Optional-plus-null with a small required core loses less information and fails more visibly. Strictness is a budget you spend where invalidity is unacceptable, not a virtue to maximize.

---

## Interview questions

### Q1 — What breaks in production without structured output, concretely?
**Testing:** whether you have personally owned the failure, or are describing it from a blog post.
**Answer:** The failure is almost never "invalid JSON" in the abstract; it is a working system that stops working when nothing you own changed. Three concrete incidents: a provider snapshot update changed formatting habits, and a downstream `json.loads` on a tool argument started throwing on step 7 of a 9-step agent run, discarding runs in front of users; a model stopped emitting an optional field it had always emitted, and code that never checked for absence null-pointer'd; and a retry-on-parse-error loop with no cap turned a model regression into a cost incident — every request paying 3–5 full inference passes. The shared root cause: prose was being treated as an interface.
**Follow-up trap:** *"So we should turn on strict mode everywhere?"* — No, and saying yes fails the senior bar. Constrain machine-facing fields; keep human-facing prose free; skip the grammar entirely for tiny fixed vocabularies; and check refusal, truncation, and subset limits, because each voids the guarantee. The correct claim is "structured output where invalidity is expensive," not "structured output everywhere."

### Q2 — A teammate says "just enable JSON mode." What is wrong with that?
**Testing:** whether you know JSON mode guarantees syntax, not shape.
**Answer:** JSON mode (OpenAI, DevDay Nov 2023) constrains the output to *parseable JSON* — and stops there. It guarantees no required keys, no value types, no enums, no key-set restrictions: a model can emit `{}` or `{"resonse": "..."}` all day in perfect JSON. The numbers make the gap vivid: prompting-only schema following on gpt-4-0613 was measured under 40% on OpenAI's own complex-schema evals, versus 93% for the 2024-08-06 gpt-4o trained for schemas, versus the 100% claim once constrained decoding is layered on. JSON mode is a floor for parsing; schema adherence is a different product, shipped 9 months later.
**Follow-up trap:** *"But doesn't JSON mode at least stop the markdown-fence problem?"* — Mostly, and that is its remaining legitimate use in 2026. But the fence problem is a *parse* problem, the cheapest one to repair (strip fences, re-parse), while the missing-key/wrong-type problem is a *contract* problem that surfaces as wrong behavior downstream, not as an exception. Fix the contract problem with a schema; do not mistake one for the other.

### Q3 — Walk me through constrained decoding mechanically, one level below "it masks logits."
**Testing:** whether you can derive the implementation, not recite the marketing.
**Answer:** Compile-time: the JSON Schema becomes a context-free grammar, the grammar a pushdown automaton, and — because tokens do not align with grammar terminals — the compiler computes, for every automaton state, which of the ~128,000 vocabulary tokens keep the prefix inside the language. The expensive insight is that over 99% of tokens are context-independent (XGrammar), so their validity is precomputed into a token-mask cache; the context-dependent remainder is checked at runtime against a persistent stack structure. Decode-time: after each sampled token, advance the automaton, build the mask (cached set + runtime-checked set), set every other logit to -inf, softmax, sample. Invalid tokens get probability exactly 0. Serving-time: overlap the CPU grammar work with GPU compute, jump-forward over fully-determined token spans, and support rollback for speculative decoding.
**Follow-up trap:** *"What breaks at token boundaries — a token that spans two grammar states?"* — That is the tokenizer–grammar mismatch problem, and naive engines handle it badly: the compiler must decide validity for multi-character tokens against every alignment, and misalignment can leave a feasible prefix that can never reach acceptance — the 2026 "Stay Within Your Bounds" work exists precisely because locally-feasible prefixes dead-end under finite token budgets. A strong answer names token-alignment as *the* core engineering problem of grammar engines.

### Q4 — Why did OpenAI choose a CFG over an FSM for Structured Outputs, and when does it matter?
**Testing:** formal-language intuition applied to product design.
**Answer:** FSMs (regex-derived, the Outlines lineage) cannot express recursive schemas — matching arbitrarily nested brackets requires a stack, i.e., a pushdown automaton. OpenAI's canonical example is a recursive UI-component tree: `children: {items: {$ref: "#"}}`, where each element can contain more elements at any depth. An FSM literally cannot count parentheses, so FSM-backed engines either reject the schema or cap depth. The cost of the CFG choice: PDA states are not precomputable the way FSM states are (infinitely many stack configurations), which is why mask computation needed the context-independent/context-dependent split and why CFG masking measured ~10x slower than JSON-schema masking in XGrammar's benchmarks — JSON schemas are mostly regular, so the FSM-class fast path covers them.
**Follow-up trap:** *"So CFG is strictly better — use it always?"* — No. Use the weakest formalism that covers your constraint: most extraction schemas are regular (flat objects, arrays of scalars) and compile dramatically faster; recursion is the exception. And note the portability trap: Anthropic's subset does not support recursive schemas at all, so a schema that works on OpenAI 400s on Anthropic — "recursion" is a per-provider capability question, not a JSON Schema question.

### Q5 — Design the output schema for extracting action items from meeting notes. Talk through your choices.
**Testing:** schema design as interface design, with subset-awareness.
**Answer:** Core shape: `{"action_items": [{"description": string, "due_date": string|null, "owner": string|null}]}` with `additionalProperties: false`. The decisions that matter: (1) `due_date` and `owner` are **nullable, not omitted** — `"required": ["description","due_date","owner"]` with type `["string","null"]` forces the model to *decide* (is there a date or not) instead of silently dropping the key, which is how absent-field bugs are born; (2) `description` is the only field that must exist, so it is the semantic core; (3) no enum on `owner` — people's names are an open vocabulary, an enum would force nearest-match hallucinations; (4) the date *format* goes in the field description ("ISO 8601, e.g. 2026-09-06"), because `"format": "date"` support varies by provider and string-length constraints are not in most subsets anyway; (5) key names are an instruction channel — 2026 work measured accuracy shifting from *key wording alone* with prompts held fixed, so `action_items` beats `items` and `due_date` beats `date`.
**Follow-up trap:** *"Why not make every field required and add minLength to guarantee quality?"* — Two failures. `minLength`/`maxLength` are outside the documented subsets — Anthropic 400s on them, and SDK transforms silently demote them to prose descriptions — so the guarantee you think you have does not exist. And forcing presence of content the model does not know produces fabricated values: a made-up owner is worse than an honest `null`. The correct lever for value quality is the repair loop plus evals, not the grammar.

### Q6 — You enabled strict mode. Validity went to 100%. Your accuracy eval dropped 6 points. Explain and fix.
**Testing:** whether you know the format tax exists and where it actually lives.
**Answer:** This is the measured quality-vs-strictness trade. "Let Me Speak Freely?" (2024) showed format restrictions degrade reasoning, with stricter formats worse — JSON's closed brackets force structural commitment before content decisions are done. The Format Tax (2026) localized the surprise: most of the loss comes from the format-requesting *instructions in the prompt*, not the decoder mask — and enforcing at the decoder compresses diversity barely further than the request already did (-0.03 bits). Fixes in order of effectiveness: put the reasoning in a free-text field *inside* the schema (constrained envelope, unconstrained thought); or two-pass — freeform generation, then a cheap reformat call under the strict schema; and re-run the A/B per model, because recent closed-weight models measured near tax-free while open-weight models still pay. A 6-point drop on an open-weight model is squarely in the published range.
**Follow-up trap:** *"So turn it off and just validate with retries?"* — No: naive prompting on 7–9B models was measured at *0% output accuracy* despite ~85% task accuracy (2026, GSM8K-class) — every answer correct, none parseable. The choice is not constrain-versus-repair; it is constrain-with-a-reasoning-channel versus repair-loop-with-measured-cost. Pick by measuring validity, accuracy, and retry-cost together, on your model.

### Q7 — Someone on your team claims constrained decoding has zero overhead. Push back precisely.
**Testing:** whether you can hold two true-sounding numbers and reconcile them.
**Answer:** Both published extremes are real and the reconciliation is the answer. Near-zero: XGrammar precomputes >99% of the token mask, measured 3.5x/10x faster masking than prior engines and up to 14x/80x end-to-end — for flat JSON schemas, warm caches, moderate batch. Far-from-zero: 3.6x–8.2x latency overhead measured on 7–9B models in some settings (2026); mask computation that scales linearly with vocabulary (PSC's motivation); and the cardinality wall — at batch 256 over 10,000-value choice sets, vLLM+XGrammar measured 7.5 req/s versus 219 req/s with precomputed trie masks, a 29x gap. Plus the compile cost everyone forgets: 10–60s on first request per schema. So the precise claim is: overhead is a function of schema class (flat ≈ free; huge enums, recursion ≈ not), batch size (CPU masking is the bottleneck exactly when GPU throughput peaks), and cache temperature.
**Follow-up trap:** *"Why does batch size make it worse instead of amortizing it?"* — The model forward pass batches on the GPU and amortizes beautifully; the grammar engine's per-sequence automaton walk and mask computation runs per-step per-sequence on the *CPU*. More batch = more GPU throughput = the CPU side, which does not vectorize across sequences with different schemas and states, becomes the constraint. That asymmetry is the whole story, and it is why engine work (context-independent precompute, vocab-independent stack classification, trie masks) is all CPU-side.

### Q8 — Design the repair loop. Where does it stop, and what happens after it stops?
**Testing:** repair economics and failure-mode honesty.
**Answer:** Anatomy: validate with pydantic → serialize errors as `loc + msg` → feed back as the next user message → retry → cap → salvage → queue. The bounds: 3 retries (instructor's default), because each retry is a full inference pass and the validity curve flattens — if the model has not fixed a named, specific error in 3 attempts, it is not a sampling accident, it is a schema or prompt problem. After the cap: field-level salvage of the last raw output (regex per field, fill what exists, null the rest), flag `needs_review`, queue for a human or a stronger model — a degraded-but-usable record beats a 500 and beats silent data loss. Two loop-health signals: same-error thrash (feedback not landing — fix the error text, which must name the field path and the corrective action) and first-attempt-validity trend (a step change means a model update, not bad luck).
**Follow-up trap:** *"Why not retry until it validates? Correctness matters more than cost."* — Because at bounded temperature the retry is not an independent sample — you can reproduce the same failure and loop until a human notices the bill. Unbounded retries are the classic cost incident: a validity regression post-update turns every request into 3–5 passes. And if correctness matters *that* much, the right spend is not more retries of the same prompt; it is a constrained decode, a better schema, or a stronger model — retries buy you maybe 2–9 nines at best, never certainty.

### Q9 — How do you evaluate structured outputs in CI, beyond "it parses"?
**Testing:** whether you know validity is the floor and can name the rest of the metric set.
**Answer:** Four layers. (1) **Contract tests, no model**: assert the schema compiles against the target provider's subset (catch the 400 and the silent SDK-strip *before* deploy), and that every constraint you rely on survives the transform. (2) **Validity metrics on live traffic**: first-attempt validity, retry-rate distribution, refusal rate, truncation rate, per-field error frequency — the field that fails most is the field whose description is bad. (3) **Accuracy against goldens**: field-level exact/semantic match on a held-out set — because a model that emits all-default values is 100% valid and 0% useful; validity without accuracy is vanity. (4) **The format-tax delta**: run the eval constrained *and* unconstrained and report both — the gap is the price of strictness on your model, and it is the number that tells you whether the reasoning-field pattern or two-pass is worth it.
**Follow-up trap:** *"Give me the one number I put on the dashboard."* — There isn't one, and asking for one is the failure mode the question is probing. Validity alone rewards deterministic garbage; accuracy alone hides parse failures behind repair costs. The honest minimum is a pair — first-attempt validity *and* field accuracy — plus the retry budget consumed, because a validity point bought with 3 extra inference passes may cost more than it earns.

### Q10 — The vendor says 100% schema adherence. Name every way you still get invalid output.
**Testing:** whether you have read the guarantee's fine print.
**Answer:** Four documented holes. (1) **Refusal** — the safety path bypasses the grammar by design: OpenAI returns a `refusal` field, Anthropic `stop_reason: "refusal"`, both with a 200 status, both billed, output not schema-conformant. (2) **Truncation** — hitting `max_tokens` cuts generation mid-array; `finish_reason: "length"` means the text is structurally incomplete and unparseable. (3) **The subset** — the guarantee covers a documented subset of JSON Schema; unsupported keywords either 400 at request time (honest) or get silently stripped by SDK transforms into descriptions (the trap — your constraint is now a suggestion). (4) **The guarantee's scope** — "adheres to schema" says nothing about value correctness; a schema-conformant wrong answer is within spec. Practical consequence: parse defensively forever — check finish/refusal fields, validate anyway, and treat the provider guarantee as removing 99% of the repair traffic, not the validator.
**Follow-up trap:** *"How do you detect truncation before you parse?"* — You do not parse first: read `finish_reason`/`stop_reason` from the response object. `"length"` → retry with a larger `max_tokens` or continuation, and fix the root cause by budgeting output tokens against the schema's plausible size (an array of 50 items needs headroom; cap `maxItems`-style bounds in your schema design). Detecting truncation *after* a JSON parse error means you lost the distinction between "model misbehaved" and "you under-budgeted" — different fixes, and the second one is yours.

### Q11 — A provider model update broke 8% of your structured calls. Walk me through the response and the prevention.
**Testing:** postmortem discipline plus schema-as-versioned-contract thinking.
**Answer:** Response, in order: alert on first-attempt-validity delta (your per-schema instrumentation, not user complaints); pin the previous model snapshot immediately — you are paying for the escape hatch, use it; triage the failures into classes (fence-wrapping, field-dropping, enum-case changes, refusal-rate change — each has a different downstream fix); fix the highest-frequency class in the prompt/schema; canary the new model with the validity SLO as the rollback trigger, not CPU or 5xx — a structured-output regression is invisible to infrastructure metrics. Prevention: treat the schema like an API contract with conformance tests *at the model boundary* — a golden set of inputs with expected-validated-outputs, run against candidate models before cutover, the same way you run contract tests against a new downstream service; and design for it upfront: subset-check at build time, avoid the keywords that silently transform, `null` over absence for anything the model might not know.
**Follow-up trap:** *"Why not just pin the old model forever?"* — Deprecation timelines end, prices move, and the vulnerability you are pinning is often a formatting habit the new model will also change later. The durable fix is the conformance suite plus the canary, because the *process* is what survives; pinning is the incident response, not the posture. Bonus signal: if your schema depends on undocumented behaviors (implied field presence, informal ordering), the update is telling you the contract was never written down — write it down.

### Q12 — Should the model's chain-of-thought live inside the structured output?
**Testing:** principal-level synthesis of the format tax, latency, and security in one design call.
**Answer:** Usually yes, as a free-text field — with three caveats earned the hard way. The pattern (`{"reasoning": string, "answer": ..., "citations": [...]}`) is the standard mitigation for the format tax: the envelope is constrained, the thinking is prose, and decoupling recovers most of the measured accuracy loss. Caveat one: the register effect is not removed by putting CoT in a field — merely *requesting* JSON measurably narrows which answers the model produces (modal share 41% → 64% in the 2026 census), so if you need diverse ideation, generate that phase unconstrained and structure it in a second pass. Caveat two: CoT inside JSON is token-expensive — escaping, quotes, and structure overhead on every reasoning token — so for cost-sensitive paths the two-pass variant (freeform, then reformat) is often cheaper than JSON-embedded CoT. Caveat three: security — a reasoning field is model-generated text your system will store, display, or feed to tools; treat it as untrusted content (the injection surface is the same as any model output), and never let it become executable instruction.
**Follow-up trap:** *"So just always two-pass then — freeform first, reformat second?"* — It is the strongest quality play and the most expensive: a second full inference pass on every call. The decision framework: human-facing answer quality dominates and budget allows → two-pass; machine-facing extraction (the 90% case) → single-pass with a reasoning field, or no reasoning field at all, because for "extract these fields" tasks the tax is small and the extraction is the point; latency-critical → single-pass constrained, no CoT, and accept the measured tax on the few reasoning-heavy cases by routing just those to the two-pass path. "Always" is the word being tested; the answer is routing, not dogma.

---

## Red flags that fail you

- "Just use JSON mode" — with no validation story and no knowledge that it guarantees syntax, not shape.
- Unbounded or unexamined retry loops; "retry until it validates."
- "Constrained decoding has zero cost." (Or its inverse, "it's always expensive" — both are unmeasured absolutism.)
- Quoting "100% schema adherence" without the conditions: subset, refusal, truncation.
- No `finish_reason`/`stop_reason` check before parsing.
- Believing the schema enforces semantics ("the enum means it picked the right category").
- Letting user-supplied schemas reach a grammar compiler unaudited.
- Required-everything schemas with no null path — hallucinated values enforced at probability 1.
- "We don't need evals, the output is guaranteed valid." Validity is the floor, not the metric.
- Being unable to name a single number: the 93→100, the <40, the 3.6–8.2x, the 29x, the 10–60s compile.
- Describing instructor/outlines/xgrammar interchangeably — engine vs repair loop vs API is a real distinction.

---

## Cheat card

```
THREE MECHANISMS (stack them, weakest → strongest)
  1 PROMPT+VALIDATE  "output JSON only" + pydantic parse + repair loop · no guarantee
  2 CONSTRAINED DECODE  schema → grammar → per-step logit mask · invalid output IMPOSSIBLE
  3 REPAIR LOOP  validate → teach-error feedback → retry ≤3 → salvage → human queue
  rule: constrain machine-facing fields · keep human prose free · validate FOREVER

HISTORY  2022 regex+parse+pray · 2021 PICARD (parser-constrained decoding)
  2023-10 Outlines (Willard & Louf): regex/JSON-Schema → FSM → logit masks
  2023 jsonformer / guidance / lm-format-enforcer · 2023-11 OpenAI JSON mode (valid JSON, NO schema)
  2024-08-06 OpenAI Structured Outputs (schema → CFG, strict:true, refusal field)
  2024-11 XGrammar v0.1 → vLLM (12/2024), SGLang, TRT-LLM (1/2025), MAX (2/2025), OpenVINO (9/2025)
  2025-11-13 Anthropic beta → GA: output_config.format + strict:true tools · XGrammar-2 2026-05

HEADLINE NUMBERS
  gpt-4o-2024-08-06: 93% trained-only → 100% claimed w/ mask (their evals) · gpt-4-0613 <40%
  first request per schema: compile <10s typical, up to 60s complex, cached after
  vocab ≈ 128K tokens (Llama-3) — naive mask checks all per step
  XGrammar: >99% of mask precomputable · 3.5x JSON / 10x CFG masking · 14x/80x e2e (Llama-3-8B, H100)
  CD overhead measured elsewhere: 3.6x–8.2x latency (7–9B, some settings) · mask cost ∝ vocab size (PSC)
  cardinality wall, batch 256, 10K-value sets: 7.5 → 219 req/s w/ precomputed trie masks (29x)
  naive 7–9B prompting: 0% output accuracy at ~85% task accuracy → repair alone is not enough
  SLOT: Mistral-7B + CD = 99.5% schema / 94% content, +25pp over Claude 3.5 Sonnet

MECHANICS  schema → (subset) → CFG → PDA → after each token: advance automaton,
  valid-token set = cached context-independent (>99%) + runtime context-dependent,
  apply -inf mask → softmax → invalid tokens p = 0 exactly
  token ≠ grammar terminal: compiler must align tokenizer with grammar (THE core problem;
  misalignment → feasible prefixes that dead-end)
  FSM vs CFG: FSM can't count brackets → no recursive schemas; CFG needs the stack tricks

PROVIDER SUBSET (Anthropic, documented; others similar but DIFFER)
  YES: basic types · enum (scalars only) · const · anyOf/allOf (limits) · $ref/$defs
       required + additionalProperties:false · formats: date-time/time/date/duration/
       email/hostname/uri/ipv4/ipv6/uuid · minItems 0 or 1 only
  NO: recursive schemas · minimum/maximum/multipleOf · minLength/maxLength · external $ref
      enum of complex types · regex backrefs/lookarounds/\b · unsupported → 400 (not silent)
  SDK transform strips unsupported → into field DESCRIPTIONS (your constraint becomes prose)
  property order: required first, then optional — parse order-free

GUARANTEE HOLES (the 100% claim, scoped)
  refusal → 200 + billed + schema broken (OpenAI: refusal field · Anthropic: stop_reason refusal)
  truncation → finish_reason "length" → invalid mid-array JSON; budget tokens, cap array size
  subset → 400 at request time, or silent SDK strip — contract-test every constraint in CI
  OpenAI strict tools: parallel_tool_calls must be false · Structured Outputs NOT ZDR-eligible

QUALITY: THE FORMAT TAX (the trap)
  format restrictions degrade reasoning; STRICTER format = WORSE (JSON worst: closed brackets)
  most of the tax is in the PROMPT REQUEST, not the decoder mask (decoder adds ≈ -0.03 bits)
  "reply in JSON" alone: modal answer 41%→64%, distinct 52→36 (diversity collapse)
  closed-weight recent models ≈ tax-free; open-weight models still pay → MEASURE per model
  fixes: freeform reasoning field inside schema · two-pass (freeform → reformat) · A/B both

REPAIR LOOP (instructor default max_retries=3; each retry = 1 full inference pass)
  pydantic ValidationError → loc+msg+type → feedback NAMES the field and THE FIX
  same-error thrash = feedback not landing → change error text / temperature / add example
  after cap: field-level salvage (regex per field) → nulls → needs_review:true → human queue
  metrics: first-attempt validity (~90%+ healthy) · retry distribution · thrash count

PROD SURFACES
  OpenAI: tools strict:true · response_format json_schema strict:true · .parse() SDK helpers
  Anthropic: output_config.format (ex-beta structured-outputs-2025-11-13) · strict:true tools
  vLLM: extra_body structured_outputs {json|regex|choice|grammar|structural_tag}
        guided_* REMOVED v0.12.0 · backends xgrammar | guidance (auto picks)
        offline: StructuredOutputsParams in SamplingParams
        reasoning models: need --structured-outputs-config.enable_in_reasoning=True (v0.11.2+)
  instructor: response_model any provider · auto-retry w/ error message · patch re-ask modes

SECURITY  schemas are INPUT: CDA/DictAttack hides jailbreaks in grammar-enforced fields
  94.3–99.5% ASR on flagships · 75.8% even vs jailbreak guardrails (CCS 2026)
  audit untrusted schemas like SQL: allowlist keywords, cap enum cardinality + compile time

WHEN NOT  tiny fixed vocab → membership check beats a CFG · one-shot human prose → tax, no gain
  cold schema on tight latency SLO → 10–60s compile · cross-field semantics → grammar CAN'T, loop instead
  open-weight model + reasoning task → measure the tax first · reasoning-heavy → two-pass or free-form field
```

## Sources

- [OpenAI — Introducing Structured Outputs in the API](https://openai.com/index/introducing-structured-outputs-in-the-api/) — launch date 2024-08-06, 100%/93%/<40% numbers, CFG-not-FSM rationale and recursive UI schema example, first-request latency <10s/60s, refusal field, parallel_tool_calls incompatibility, ZDR ineligibility; accessed 2026-09-06
- [OpenAI — Structured model outputs (docs)](https://platform.openai.com/docs/guides/structured-outputs) — current API surfaces (`text.format`, function calling strict mode), "always use Structured Outputs instead of JSON mode", JSON mode vs Structured Outputs comparison; accessed 2026-09-06
- [Anthropic — Structured outputs (docs)](https://docs.claude.com/en/docs/build-with-claude/structured-outputs) — `output_config.format` GA out of beta `structured-outputs-2025-11-13`, strict tool use, supported subset and not-supported list, regex pattern limits, 400-on-unsupported, property ordering, refusal and max_tokens invalid-output behavior, SDK schema transformation; accessed 2026-09-06
- [vLLM — Structured Outputs (docs)](https://docs.vllm.ai/en/latest/features/structured_outputs.html) — `structured_outputs` parameters, `guided_*` removal in v0.12.0, xgrammar/guidance backends, `StructuredOutputsParams` offline inference, `--structured-outputs-config.enable_in_reasoning` for reasoning models; accessed 2026-09-06
- [XGrammar — GitHub](https://github.com/mlc-ai/xgrammar) and [MLC blog: Achieving Efficient, Flexible, and Portable Structured Generation with XGrammar](https://blog.mlc.ai/2024/11/22/achieving-efficient-flexible-portable-structured-generation-with-xgrammar) — context-independent token precompute (>99%), 3.5x/10x masking and 14x/80x e2e numbers, Llama-3 ~128K vocab, engine integrations timeline (vLLM 2024-12, TRT-LLM 2025-01, MAX 2025-02, OpenVINO 2025-09, Mirai 2025-12, XGrammar-2 2026-05), tech report arXiv:2411.15100; accessed 2026-09-06
- [Tam et al. — Let Me Speak Freely? A Study on the Impact of Format Restrictions on Performance of LLMs (arXiv:2408.02442)](https://arxiv.org/abs/2408.02442) — format restrictions degrade reasoning, stricter constraints degrade more; accessed 2026-09-06
- [Lee, D'Antoni, Berg-Kirkpatrick — The Format Tax (arXiv:2604.03616)](https://arxiv.org/abs/2604.03616) — dominant cost in the prompt request not the mask, closed-weight models near tax-free, decoupling recovers accuracy; accessed 2026-09-06
- [Parikh — Structured Output Collapses Answer Diversity Across 44 Language Models (arXiv:2607.18476)](https://arxiv.org/abs/2607.18476) — request-only diversity collapse 41%→64% / 52→36, decoder enforcement adds -0.03 bits; accessed 2026-09-06
- [Galeone et al. — When Correct Isn't Usable: Improving Structured Output Reliability in Small Language Models (arXiv:2605.02363)](https://arxiv.org/abs/2605.02363) — 85% task accuracy with 0% output accuracy on naive prompting, constrained decoding 3.6x–8.2x latency overhead in some settings; accessed 2026-09-06
- [Wang et al. — SLOT: Structuring the Output of Large Language Models (arXiv:2505.04016)](https://arxiv.org/abs/2505.04016) — Mistral-7B + constrained decoding 99.5% schema / 94% content, +25/+20pp over Claude 3.5 Sonnet; accessed 2026-09-06
- [Li et al. — Efficient Grammar-Constrained Decoding via Parser Stack Classification (arXiv:2608.03065)](https://arxiv.org/abs/2608.03065) — mask computation scaling linearly with vocabulary, up to 700x/30x faster masking; accessed 2026-09-06
- [Xu, Bouyarmane — Trie Automata for Constrained Decoding over Large Finite Sets (arXiv:2608.12574)](https://arxiv.org/abs/2608.12574) — cardinality wall, 0.65μs vs 5.8μs per-step, 219 vs 7.5 req/s at batch 256 (29x), sub-100ms compile to K=10,000; accessed 2026-09-06
- [Collura et al. — Stay Within Your Bounds: Distance-Guided Decoding for Guaranteed CFG Compliance (arXiv:2608.28229)](https://arxiv.org/abs/2608.28229) — tokenizer-grammar mismatch and token budgets causing feasible prefixes to dead-end; accessed 2026-09-06
- [Le — Schema Key Wording as an Instruction Channel in Structured Generation under Constrained Decoding (arXiv:2604.14862)](https://arxiv.org/abs/2604.14862) — key wording as instruction channel, model-dependent prompt vs schema sensitivity; accessed 2026-09-06
- [Cruz — ATLAS-RTC: Closing the Loop on LLM Agent Output with Token-Level Runtime Control (arXiv:2603.27905)](https://arxiv.org/abs/2603.27905) — in-decoding drift detection with bias/mask/rollback, +20 to 37.8pp first-attempt success, up to 88% latency reduction; accessed 2026-09-06
- [Zhang et al. — When Grammar Guides the Attack: Constrained Decoding Attack (arXiv:2503.24191)](https://arxiv.org/abs/2503.24191) — CDA/DictAttack, 94.3–99.5% ASR on flagship models, 75.8% against jailbreak guardrails, CCS 2026; accessed 2026-09-06
- [Song et al. — Empirical Study for Structured Output Control in LLMs for Software Engineering (arXiv:2606.09395)](https://arxiv.org/abs/2606.09395) — structure-enforcing tools necessary but insufficient; syntax errors eliminated while structural/semantic errors persist; accessed 2026-09-06
- [Willard, Louf — Efficient Guided Generation for Large Language Models (arXiv:2307.09702)](https://arxiv.org/abs/2307.09702) — the Outlines lineage: regex/JSON Schema to FSM, efficient logit masking; accessed 2026-09-06
- [instructor — README](https://github.com/567-labs/instructor) — `response_model`, automatic validation retries with error feedback (`max_retries=3`), provider-agnostic patch and JSON modes; accessed 2026-09-06

## Changelog
- 2026-09-06 — created
