# Guardrails In/Out: Guardrails AI, NeMo, Validation Layers, PII, Toxicity

> **Track:** T07 Agentic AI · **Time:** 2.5h · **Prereqs:** `T07-structured-output` · **Updated:** 2026-09-06
> **Module id:** `T07-guardrails` · **Tags:** security, critical
> **Lab:** `labs/py/19-guardrails/`

## The 30-second version

A guardrail is deterministic input/output validation and policy enforcement wrapped around a nondeterministic model, and everything else is taxonomy: you **classify** (topics, PII, jailbreak, toxicity), **verify** (schema, facts, constraints), **transform** (redact, mask, pseudonymize), and **route** (block, fix, retry, escalate to a human). The libraries, Guardrails AI's validators, NeMo Guardrails' rail flows, Llama Guard, Presidio, the platform filters in Azure OpenAI and Bedrock, are prebuilt validators; the actual engineering is choosing **where** each guard runs (in-app, at a gateway, or in the provider platform), what it costs in latency and per-call dollars, and what happens when it fails, because fail-open and fail-closed are per-risk decisions, not global ones. Model-based classifiers buy coverage (Llama Guard 3 hits F1 0.939 with a 4% false-positive rate on Meta's English benchmark) at the price of a full model forward pass on every call, so real systems tier them: deterministic checks sub-millisecond on everything, statistical PII detectors where PII can enter, and model classifiers only where the risk justifies hundreds of milliseconds. And the honest caveat that proves you have shipped: every guardrail is a false-positive machine on legitimate traffic, so you measure over-blocking on real logs before you measure blocking on red-team suites, or your guardrail ships as a UX bug.

## Why this gets asked

Because the interviewer has personally shipped an agent that leaked something or got jailbroken through a channel nobody scanned. Two war stories dominate, and they are the ones you should answer to: (1) an agent that had PII scanning on user input, none on **tool results**, and faithfully echoed a customer's card number from a database row into a Slack channel; (2) a "safety-reviewed" prompt that a user jailbroken via a base64-encoded paste, because the guard was a keyword blocklist and encoding defeats every keyword blocklist. What they are probing is whether you can design the **validation architecture**, the placement, ordering, latency budget, failure policy, and measurement of guards, or whether you will just say "we use Guardrails AI" and stop. The follow-up ladder is predictable: library name, then where it runs, then what happens when it's down, then how you know it works, then what it costs. Candidates who only answer the first rung fail. This module is the other four rungs.

---

## Lineage: past → present → future

**What came before.** Before LLM guardrails there were content filters, and content filters were regex blocklists and keyword lists. That era's pain is worth naming because it explains every design decision since: blocklists are trivially defeated by paraphrase, homoglyph substitution, whitespace, leetspeak, and encoding, and they over-block legitimate usage (the medical chatbot that cannot discuss breast cancer because "breast" is on the list). The LLM era made this worse before it made it better: safety moved **inside the model** via RLHF training, which you could not audit, version, or turn down, and which produced the "safety theater" backlash, jailbreak research (the XSTest paper, arXiv 2308.01263, was written in 2023 specifically to measure *exaggerated safety*, models refusing benign prompts), and a wave of jailbreak-prompt benchmarks where a fixed prompt defeated most deployed filters. Meanwhile Microsoft had built **Presidio** (2018, pre-LLM) for PII de-identification in logs and documents, with a recognizer architecture, regex, checksum, NER, context words, that remains the backbone of PII handling today. The specific pain that killed the pure-blocklist approach: you were playing whack-a-mole against paraphrase with a linear-time string matcher, you had no coverage of semantics at all, and you could not prove to a regulator what your filter did or did not catch. Guardrails as a distinct discipline emerged in 2023 when two things landed: OpenAI's free **moderation endpoint** (text classification, scored categories) and **NeMo Guardrails** (NVIDIA, EMNLP 2023, arXiv 2310.10501), which reframed the problem as *programmable rails around the model* rather than *safety training inside the model*. **Llama Guard** (Meta, Dec 2023, arXiv 2312.06674) then showed the other half: a small LLM fine-tuned as a classifier, auditable and self-hostable, covering semantic attacks no regex could see.

**Where it stands now.** The 2026 deployed stack is layered, and the consensus has three tiers of validator plus an orchestration question. Tier 1, deterministic: JSON Schema checks, regex, banned URLs, blocklists, canary/leak detection, all sub-millisecond, all in-process. Tier 2, statistical: **Presidio** for PII, using pattern match plus checksum plus context words plus optional NER; its entity library now spans roughly 80 predefined entity types across 20-plus jurisdictions (US SSN, UK NHS number, Indian Aadhaar, German tax ID, and so on). Tier 3, model-based classifiers: **Llama Guard 3** (8B, 14 MLCommons hazard categories, 8 languages, prompt and response classification, F1 0.939 / FPR 0.040 on Meta's English response-classification benchmark versus GPT-4 at 0.805 / 0.152), **Llama Guard 4** (12B, multimodal, dense, single-GPU), ShieldGemma, OpenAI's free `omni-moderation-latest` (13 categories, text and image), and the managed platform filters: Azure OpenAI's content filters (4 harm categories at 4 severity levels, plus optional jailbreak, protected-material, PII, and prompt-shield classifiers) and AWS Bedrock Guardrails (6 content categories including Prompt Attack, denied topics, word filters, PII block/mask, contextual grounding checks, and an `ApplyGuardrail` API that runs guards without invoking the model). Two frameworks own orchestration: **Guardrails AI** (Python, `Guard().use(validator, on_fail=...)`, a Hub of 65 validators now shipping as individual PyPI packages) and **NeMo Guardrails** (5 rail types: input, dialog, retrieval, execution, output; flows written in Colang). The **live disagreements** are genuine: (a) *model-based versus deterministic validators* — coverage versus latency and cost, with the pragmatic answer being tiering rather than either; (b) *where guardrails belong*, in your app, at a shared LLM gateway, or in the provider platform, and the strongest argument for the app is that only it knows which tool results are untrusted and which risk tiers matter; (c) *fail-open versus fail-closed*, where Azure's own documentation openly states that if its content filter errors, the request completes **without filtering** — a documented fail-open you must design around. Also live and unresolved: Guardrails AI announced in July 2026 that its hosted remote inferencing is being discontinued (validators become standard PyPI packages, cutoff August 25, 2026), a reminder that guardrail dependencies are supply-chain decisions too.

**Where it's heading.** High confidence: **policy-as-code**. Guardrail configurations are becoming versioned artifacts, YAML/Colang/OPA-style policies that are reviewed, tested against red-team and benign corpora, and rolled out with canaries, rather than hand-tuned sliders in a console. Bedrock's automated-reasoning checks (natural-language policies validated as logical constraints) and MLCommons' AILuminate benchmark work point the same way: policies you can state, test, and audit. High confidence: **convergence into serving stacks**. Schema-based guards (structured output, constrained decoding) and model-based guards (moderation classifiers) are moving into the inference layer itself, vLLM/OpenAI-compatible serving already runs Llama Guard sidecars at hundreds of calls per second, and OpenAI's Responses API now returns moderation scores *inline* with generation rather than as a separate call. Medium confidence: **PII detection goes local and on-device**, driven by regulation and by the obvious point that sending text to a PII-detection SaaS to find out you should not have sent the text is a self-defeating design; Presidio's move to a community-owned project and the LiteLLM-proxy PII-masking recipes are early signals. Speculative but plausible: guardrail **effacy benchmarking becomes a procurement requirement**, the Guardrails Index (Feb 2025, 24 guardrails across 6 categories) is the first serious attempt, and buyers starting to demand FPR-on-benign-traffic numbers the way they demand uptime SLAs. Treat that as direction of travel, not settled practice.

---

## Mental model

**Pipes and filters with a latency budget, where every filter is a valve that can block, fix, or pass-with-alarm, and the budget is per-layer, not per-system.**

```
 user / tool result
        │
        ▼
 ┌──────────────────── INPUT GUARDS ────────────────────┐
 │ topic allowlist (deterministic)        < 1 ms        │
 │ PII scan + pseudonymize (statistical)  ~50-300 ms *   │
 │ jailbreak classifier (model-based)    ~100-400 ms *  │
 └──────────────────────────────────────────────────────┘
        │  budget example: 200 ms p99 for ALL input guards
        ▼
 ┌────────────────── MODEL / AGENT LOOP ────────────────┐
 │ (the model is nondeterministic; the guards are not)  │
 └──────────────────────────────────────────────────────┘
        │
        ▼
 ┌──────────────────── OUTPUT GUARDS ────────────────────┐
 │ schema check (deterministic)           < 1 ms        │
 │ canary / leak scan (deterministic)     < 1 ms        │
 │ PII scan (statistical)                ~50-300 ms *  │
 │ toxicity / groundedness (model)        ~100-400 ms * │
 └──────────────────────────────────────────────────────┘
        │
        ▼
   tools: each with its OWN permission gate (risk tiers,
          least-privilege credentials, per-tool guards)

 * practice numbers, deployment- and text-length-dependent.
   The shape is the point: deterministic < statistical < model.
```

Three rules fall out of the diagram:

1. **Order by cost ascending.** Cheap deterministic guards run first and often make expensive ones unnecessary. A jailbreak regex catching the top-10 known attacks filters most junk traffic so the model-based classifier only sees the residue.
2. **Every guard carries its fail policy.** `BLOCK` (fail-closed), `FIX` (deterministic transform, e.g. redact and continue), `PASS+LOG` (fail-open with an alarm and an audit trail), `ESCALATE` (human in the loop). Assign per risk, never globally.
3. **The pipes are as important as the filters.** A guard that only exists on the user-input pipe is decoration once you have tools, because untrusted content arrives through the tool-result pipe too.

---

## How it actually works

### 1. The three validator families (and their real mechanisms)

**Deterministic validators** are pure functions: JSON Schema validation, regex, exact-match blocklists, banned-URL/domain checks, canary strings, length and range checks. Sub-millisecond, in-process, unit-testable, zero inference cost. Their weakness is semantics: a regex sees `4111 1111 1111 1111` but not "my card is the one ending in the digits you already have on file." Presidio's own checksum recognizers are the best example of how far determinism gets you: a credit card is validated as 12-19 digits **plus a Luhn checksum**, a US SSN as 9 digits plus context words, an Indian Aadhaar as 12 digits plus checksum. Deterministic validators give you *high-precision detection of well-formed identifiers* and nothing else.

**Statistical validators** sit in the middle: Presidio's analyzer runs its recognizer ensemble and scores each candidate entity with a confidence, boosted or cut by **context words** ("passport", "DOB", "account number" near a digit string raise the score). The German postcode recognizer `DE_PLZ` documents this honestly: 5 digits alone is a terrible signal, so its base confidence is 0.05 and it only produces actionable results when address-context words are present. You tune per-entity thresholds to trade recall against false positives, which is a product decision (is blocking 1 in 100 legitimate messages acceptable?) masquerading as a config value.

**Model-based validators** are LLM classifiers used as guards. Mechanically, Llama Guard works like this: it is a Llama-3.1-8B model fine-tuned to emit `safe` or `unsafe\nS<n>` for the violated categories, with **the policy applied via the chat template** — the same model classifies *user prompts* and *model responses* under different policies, and Meta's model card explicitly frames input filtering versus output filtering as complementary: input filtering catches harm before the model responds, output filtering lets the model attempt a safe response and only censors the result. To get a score rather than a label, you read the **probability of the first generated token** and threshold it. The performance numbers worth memorizing: on Meta's English response-classification benchmark, Llama Guard 3 posts F1 0.939 / FPR 0.040 versus Llama Guard 2's 0.877 / 0.081 and GPT-4 zero-shot's 0.805 / 0.152, and it explicitly curates *benign* multilingual data to keep the false-positive rate down. The cost side: this is a full model forward pass per guarded message, hundreds of milliseconds deployment-dependent, and an INT8 quantized variant ships with roughly 40% smaller checkpoints for cheaper deployment. Llama Guard 4 (12B, dense, pruned from Llama 4 Scout by deleting all 16 routed experts and keeping the shared expert) adds multimodal input at single-GPU scale.

### 2. PII: recognizers, redaction, pseudonymization, and the re-hydration trap

Presidio's architecture is the reference design because it separates the problem cleanly: an **Analyzer** (registry of recognizers, each declaring entities, patterns, context, checksums, and a score) and an **Anonymizer** (operators applied to detected spans: `redact`, `replace`, `mask`, `hash`, `encrypt`, custom). You extend it by registering recognizers, deny-lists, allow-lists, or **remote recognizers** that call Azure AI Language or your own NER service. The operators are where the architecture decision lives:

| Operator | What it does | Reversible? | Use when |
|---|---|---|---|
| `redact` | destroys the value (`<PERSON>`) | never | value has no downstream use |
| `mask` | partial reveal (`*****1111`) | never | user needs to recognize, not use |
| `hash` / `encrypt` | keyed transform | by key holder | you must re-identify later |
| `replace` / pseudonymize | swaps value for a stable fake (`PERSON_7`) | via mapping | the model must *reason over* the text and keep referents consistent |

**Pseudonymization is the trap.** Replacing `Jane Smith` with `PERSON_1` everywhere keeps the text coherent and referentially consistent, which is why you use it instead of blind redaction, but it creates a mapping that (a) is itself PII, (b) must live somewhere, and (c) enables **de-anonymization** if it leaks alongside logs. Classic result: sparse auxiliary data re-identifies "anonymized" records (Narayanan & Shmatikov's Netflix-prize de-anonymization, 2008); LLM-era result: pseudonymized text still carries style, context, and rare facts that re-identify. The discipline that survives an interview: **re-hydration happens exactly once, in the final render path, under a per-request mapping that is destroyed after render.** Never let the model see real values it does not need; never let pseudonyms reach the user; never log the mapping; never persist the map across sessions. And the failure that actually happens in production: output guards scan the *model's* text for PII, but the pseudonym map gets applied naively at render time and re-inserts a *different* user's real name because the mapping keyed on span index, not token. Key the map by token, verify at render.

Also know the boundary the Presidio docs state plainly: automated detection **does not guarantee** finding all sensitive information, so it is a layer, not a boundary. The companion control is not scanning harder, it is least privilege (the tool that cannot read card numbers cannot leak them), which is why this module is a sibling of tool risk tiers, not a replacement.

### 3. Jailbreak and injection classification, honestly

Jailbreak detection is where model-based guards earn their cost. The pipeline almost everyone converges on: a cheap deterministic prefilter (known-prompt signatures, encoding detection, "ignore previous instructions" style markers) handles the long tail of copy-paste attacks, and a model classifier handles novel and paraphrased ones. Llama Guard 3's tool-use training is instructive: Meta trained it specifically on search-tool-call and code-interpreter content (F1 0.856 / FPR 0.174 and 0.885 / 0.125 respectively on those capabilities), including *benign borderline* data curated to suppress false positives, because a guard that blocks "how do I kill a process in Linux" (a real example from Meta's card) is a guard that gets disabled by the product team. Platform classifiers now ship this as a first-class category: Bedrock's content filters include a **Prompt Attack** category covering jailbreaks, prompt injections, and prompt leakage, and Azure's **Prompt Shields** split user-prompt attacks from **indirect attacks** (instructions embedded in retrieved documents), which is the agent-specific threat: your guard must scan tool results and RAG chunks, not just the user's message. OpenAI's moderation categories are content-harm oriented (13 categories like `hate/threatening`, `illicit/violent`, `violence/graphic`), so it complements rather than replaces jailbreak classifiers.

The economics matter at scale: every guarded message pays the classifier. At hundreds of ms and a model call per message, the difference between scanning *every* turn and scanning *suspicious* turns is your entire latency budget, hence prefilter-then-classify, sampling for low-risk traffic, and running the classifier asynchronously (score arrives after render; if it flags, you retract/suppress downstream actions) — the same pattern OpenAI documents for inline moderation, where streaming scores arrive only after the full output is available, not per-delta.

### 4. Orchestration: fail policies and repair loops

A guard's decision is four-valued: pass, fix, block, escalate. The interesting design space is **what happens on violation and on failure**, which are different events:

- **On violation** (guard matched): `FIX` and continue when the fix is deterministic and safe (redact PII, strip the banned domain, re-ask with feedback). Guardrails AI's `on_fail` actions and its re-ask loop, where a failed validator re-prompts the model with the error appended, are the canonical implementation; NeMo's self-check flows (`self check facts`, `self check hallucination`) do the same in Colang. Repair loops cost tokens and a second model call, so cap them (retry count, and a fallback to block after N).
- **On failure** (guard errored/timed out): this is the fail-open/fail-closed decision, and it must be **per risk**. Pseudonymous internal summarizer's PII detector times out? Log and continue (fail-open with alarm). Refund-agent's jailbreak classifier times out? Block and show a safe message (fail-closed). The industry quietly defaults to fail-open because blocking on a 500 from a moderation API looks like an outage, and that default is how incidents happen: Azure documents that when its filter system errors, the request completes *without content filtering* (the response contains `content_filter_error` telling you so) — meaning "the platform handles it" silently becomes "the platform skipped it." Your architecture must decide, per guard, whether that documented behavior is acceptable, and if not, run a redundant app-side guard for exactly that risk.

### 5. Where guardrails run, and why layers beat chokepoints

Three placements, each with a real reason to exist:

- **In the app** (per-request, in-process or sidecar): the only place that knows request context, which tool results are untrusted, which user this is, and which risk tier the action carries. Deterministic and statistical guards belong here (sub-ms to ~100 ms).
- **At an LLM gateway / proxy** (shared service, e.g. LiteLLM-style): the place for org-wide policy, one enforcement point across many apps, and where PII masking before provider egress matters (Presidio docs ship a LiteLLM-proxy masking recipe for precisely this reason: don't send the PII to the provider at all).
- **In the platform** (Azure content filters, Bedrock Guardrails, OpenAI moderation): always-on, zero marginal latency for you, versioned by the vendor, and **not configurable in the ways that matter** (Azure's severity thresholds are filter-level; you cannot see the classifiers). Bedrock's `ApplyGuardrail` API is the notable hybrid: run platform guards on arbitrary text without invoking the model, so platform guards become callable building blocks rather than a fixed pipe.

Why layers beat one chokepoint: a single gateway guard cannot see tool results, per-user context, or downstream actions, and its failure is a single point of total bypass. Defense in depth here is not ceremony: input guards catch the user, output guards catch the model, tool gates catch the *consequences* (a jailbroken model with no refund tool cannot refund). The guard that matters most is often the one on the action, not the one on the text.

---

## Build it from scratch

A compact layered guard pipeline with per-guard fail policies and reversible redaction. `labs/py/19-guardrails/` builds it against a fake PII corpus and a stub classifier, with tests for each fail policy.

```python
# untested sketch
import json, re
from dataclasses import dataclass, field
from typing import Callable, Literal

Policy = Literal["block", "fix", "log", "escalate"]   # fail-closed -> fail-open order

@dataclass
class Guard:
    name: str
    fn: Callable[[str, "GuardState"], str | None]     # None = pass
    on_violation: Policy
    on_error: Policy                                   # THE per-risk decision
    cost_ms: int = 0                                   # for budget accounting

@dataclass
class GuardState:
    pseudonyms: dict = field(default_factory=dict)     # token -> real value; NOT logged
    hits: list = field(default_factory=list)          # audit trail (no raw PII)

PII = {"ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
       "card": re.compile(r"\b(?:\d[ -]?){13,19}\b"),
       "email": re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")}

def redact(text, st):
    for kind, pat in PII.items():
        def swap(m, kind=kind):
            tok = f"<{kind}:{len(st.pseudonyms)}>"
            st.pseudonyms[tok] = m.group(0)           # deterministic map, keyed by TOKEN
            st.hits.append((kind, tok))
            return tok
        text = pat.sub(swap, text)
    return text

def jailbreak_stub(text, st):
    markers = ("ignore previous", "disregard all", "developer mode", "you are danyl")
    return "looks like a jailbreak template" if any(m in text.lower() for m in markers) else None

def has_canary(text, st, canary="CANARY_7f3a91"):
    return "system-prompt leak" if canary in text else None

def schema_ok(text, st, required=("action", "args")):
    try:
        obj = json.loads(text)
        missing = [k for k in required if k not in obj]
        return f"missing keys: {missing}" if missing else None
    except json.JSONDecodeError as e:
        return f"not json: {e}"

INPUT = [Guard("pii_in", redact, "fix", "log", 5),
         Guard("jailbreak", jailbreak_stub, "block", "block", 2)]   # fail-closed both ways
OUTPUT = [Guard("schema", schema_ok, "block", "log", 1),
          Guard("leak", has_canary, "block", "escalate", 1)]

def run_guards(text, guards, st):
    for g in guards:
        try:
            reason = g.fn(text, st)
        except Exception as e:
            reason, pol = f"guard error: {e}", g.on_error
        else:
            pol = g.on_violation if reason else None
        if not reason:
            continue
        st.hits.append((g.name, pol, reason))
        if pol == "fix":
            text = g.fn(text, st) or text            # e.g. redaction is idempotent-ish
        elif pol == "block":
            raise Blocked(g.name, reason)
        elif pol == "escalate":
            raise NeedsHuman(g.name, reason)
        # "log" -> continue, alarm fires from st.hits downstream
    return text

def hydrate(text, st):                                # re-hydration: EXACTLY ONCE, at render
    for tok, val in st.pseudonyms.items():
        text = text.replace(tok, val)
    return text

def handle(user_msg, agent) -> str:
    st = GuardState()
    user_msg = run_guards(user_msg, INPUT, st)        # model sees pseudonyms only
    raw = agent(user_msg)                             # may call tools; each has its own gate
    raw = run_guards(raw, OUTPUT, st)
    return hydrate(raw, st)                           # real values restored for THIS user only
```

Fifty lines, honestly marked, and every load-bearing decision is visible: `on_error` differs per guard (PII scan fails open with a log, jailbreak and canary fail closed), the pseudonym map is keyed by token and never enters `st.hits`, `hydrate` exists only in the render path, and output guards run on the model's text *before* re-hydration so the leak scan sees what will actually ship. What the sketch omits that production needs: real Presidio instead of three regexes, a model-based classifier behind the stub, per-guard latency accounting against the budget, and the async retraction path for streaming.

---

## How it's done in production

**Guardrails AI.** Validators are pip packages (`pip install guardrails-ai-regex-match`), composed into a `Guard` with per-validator `on_fail` actions (`EXCEPTION`, `FIX`, `REFRAIN`, custom): `Guard().use(CompetitorCheck([...], on_fail=OnFailAction.EXCEPTION), ToxicLanguage(threshold=0.5, validation_method="sentence"))`. The Hub lists 65 validators across categories (brand risk, factuality, jailbreaking, data leakage, code exploits, formatting), with PII detection backed by Presidio and injection detection by Rebuff. It can run as a Flask server (`guardrails start`) fronting an OpenAI-compatible endpoint. Operational facts to know: the **Guardrails Index** (Feb 2025) benchmarks 24 guardrails across 6 categories, and as of July 2026 the company is discontinuing hosted remote inferencing, with validators moving fully to standard PyPI packages (cutoff August 25, 2026), which simplifies self-hosting but means the CLI/`guardrails configure` workflow is in flux.

**NeMo Guardrails.** Five rail types, input, dialog, retrieval, execution, output, configured in `config.yml` plus Colang `.co` flow files. The reference config is worth memorizing because it is the clearest expression of the pattern in any framework: input flows `check jailbreak` and `mask sensitive data on input` (with `sensitive_data_detection: entities: [PERSON, EMAIL_ADDRESS]`), output flows `self check facts` and `self check hallucination`. Dialog rails are NeMo's differentiator: Colang lets you script conversation flows, so fact-checking runs only for the question types that need it. Async-first, Python 3.10-3.13, ships an evaluation CLI and built-in library of self-checks and jailbreak/injection detectors. Released version 0.23.0.

**Llama Guard 3 / 4.** Self-hostable classifier: 8B (text, 8 languages, 14 hazard categories S1-S14) or 12B multimodal, INT8 variant for cheaper serving, first-token probability for scores, prompt and response classification via chat-template policy selection. Runs on vLLM/SGLang with an OpenAI-compatible API, which is how it becomes a gateway-side microservice at hundreds of calls per second rather than an in-process dependency.

**Presidio.** Analyzer + Anonymizer (+ image redactor, structured-data module). Roughly 80 predefined entities across 20-plus jurisdictions, pluggable NLP engines (spaCy small for latency, transformers for recall, GPU supported), custom and remote recognizers, `encrypt`/decrypt operators for reversible de-identification, and a documented recipe for masking LLM calls behind a LiteLLM proxy. Community-owned as of the project's transition to the Data Privacy Stack organization.

**Platform filters.** Azure OpenAI: 4 harm categories (hate, sexual, violence, self-harm) at 4 severity levels (safe is annotated, not filtered), thresholds configurable per prompt and per completion, plus optional jailbreak detection, protected material (text/code), PII, groundedness (streaming-only, specific regions), Prompt Shields (user + indirect attacks), and Task Adherence for agents. Failure semantics you must handle: harmful input prompt returns HTTP 400; filtered completion returns `finish_reason: content_filter`; **filter-system error returns 200 with content and an error note in `content_filter_results`** (documented fail-open). AWS Bedrock Guardrails: content filters in 6 categories including Prompt Attack, denied topics (natural-language topic definitions, e.g. blocking investment advice), word filters (exact match, profanity option), sensitive-information filters (probabilistic PII detection, block or mask, custom regex), contextual grounding (groundedness + relevance for RAG), automated reasoning checks, versioned guardrails, and `ApplyGuardrail` to run the policy standalone. Note their documented log behavior: blocked content appears as plaintext in model-invocation logs, so log retention policy is part of your guardrail policy. OpenAI: `omni-moderation-latest`, free, 13 categories with 0-1 scores, text plus images (up to 20 MB), inline moderation results in the Responses API (covering tool-call arguments and outputs, not tool names/descriptions), and the documented caveat that the underlying model upgrades continuously, so custom thresholds on `category_scores` need recalibration over time.

### What breaks at scale

| Symptom | Cause | Fix |
|---|---|---|
| p99 latency doubles after guardrail rollout | model-based guards in the hot path, serialized | deterministic prefilter first, tier/sample classifier calls, run async where retractable |
| legit medical/legal traffic blocked (breast cancer, "kill the process") | blocklist/low-threshold classifier false positives | threshold per entity/category, allow-lists, measure FPR on benign production traffic, XSTest-style exaggerated-safety suite |
| jailbreaks slip through despite a jailbreak guard | paraphrase/encoding defeats regex prefilter; guard never saw novel variants | model-based classifier behind the prefilter; encode detection; red-team suite in CI; treat detection as probabilistic, add the tool-permission backstop |
| canary leak detected weeks late or never | canary scanned only on final answer, not tool results/summaries | scan every text that leaves the trust boundary; distinct canaries per surface; alert on hit, don't just log |
| guard "off" in prod, discovered after an incident | fail-open default shipped for UX; filter-error path unhandled | explicit `on_error` per guard; alarm on guard errors; Azure's `content_filter_error` path must be monitored |
| PII reaches provider/logs despite masking | guard on user input only; tool results, RAG chunks, or the pseudonym map itself leaked | scan every ingress surface incl. tool results; gateway-side masking (LiteLLM+Presidio recipe); map never logged, destroyed post-render |
| re-hydration inserts wrong user's PII | pseudonym map keyed by span index or shared across requests | per-request map keyed by token; hydrate exactly once in the render path; verify at render |
| block rate spikes after a routine dependency update | moderation model silently upgraded (OpenAI documents this); classifier drift | pin model versions where possible; golden-set regression tests on version bump; monitor score distributions, not just binary flags |
| streaming answers render, then get retracted constantly | output guard runs after full output (scores arrive post-stream) | pre-stream risk gate for high-risk intents; guard only the actionable parts (tool args, links) mid-stream |
| blocked content readable in logs by wide audience | Bedrock-style plaintext logging of blocked content; over-broad log access | treat guard logs as PII-bearing; retention + ACL policy as part of guardrail design |
| "platform handles it" gaps found post-launch | no inventory of what platform filters actually cover (e.g. no tool results, no custom policy, documented fail-open) | write the coverage matrix: risk x surface x layer; add app-side guards only for the gaps |

**Instrument per guard, not per system**: per-guard violation rate, error rate (fail-open events are your top alert), p50/p99 latency, false-positive rate on sampled benign traffic, and score-distribution drift. The block rate alone tells you nothing; the *ratio* of blocked-benign to blocked-malicious is the number your product team will ask for.

---

## Tradeoffs & when NOT to use it

- **Internal tools with trusted, authenticated users: skip heavy PII scanning.** If the input is your own employees' queries against your own data and the egress boundary is already enforced at the gateway, per-request statistical PII detection is a latency tax buying little. Move the control to the egress point (one mask config) instead of every request.
- **Rapid prototyping: blocklists and the provider's built-in filters genuinely suffice.** A deny-list, a schema check, and the platform's content filter will carry a demo. The failure is forgetting to revisit: write the coverage matrix on day one even if most rows say "not yet."
- **The provider's filters already cover your risk: don't double-scan.** If your sole exposure is generic content harm on Azure OpenAI, its built-in 4-category filter plus your blocklist is a complete answer; adding your own toxicity classifier duplicates cost and adds a second fail-open path. App-side guards exist for the gaps, tool results, custom policy, PII, reversibility, not for virtue.
- **Don't buy a model-based classifier for a deterministic problem.** If the failure mode is "output must match this schema" or "no links to internal domains," a regex or schema check is faster, free, testable, and immune to drift. Llama Guard-class classifiers are for *semantic* risks: jailbreaks, novel toxicity, contextual PII.
- **Guardrails AI when your problem is really structured output:** its roots are in schema-validated generation and repair loops; if you just need JSON conformance, constrained decoding (T07-structured-output) is the cheaper primitive, and the guard framework is overhead. Also weigh the 2026 packaging transition (PyPI validators, hosted inferencing sunset) before standardizing on its server mode.
- **NeMo Guardrails when you don't need dialog scripting:** Colang is a real learning investment and its value is flow control (fact-check only these question types). If your guards are stateless input/output checks, the framework is ceremony; a 50-line pipeline like the one above is easier to own.
- **Fail-closed everywhere is a UX outage with extra steps.** Blocking all traffic because a moderation API 500'd is how guardrails get removed. The per-risk fail policy is the design; revisit it whenever the risk or the dependency changes.
- **Don't scan what you can prevent.** The cheapest PII guard is a tool that cannot return card numbers to the agent context at all (projection at the tool boundary). Detection is for what prevention cannot guarantee; spend your architecture budget on least privilege first.

---

## Interview questions

### Q1 — What is a guardrail, and what are the four things every guardrail does?
**Testing:** whether you have a taxonomy or just library names.
**Answer:** Guardrails are deterministic validation and policy enforcement around a nondeterministic model, and every one of them does one or more of four verbs: **classify** (jailbreak, toxicity, topic, PII type), **verify** (JSON Schema, facts/groundedness, numeric constraints), **transform** (redact, mask, pseudonymize, reformat), and **route** (pass, block, retry-with-feedback, escalate to a human). The libraries are prebuilt validators, Guardrails AI has 65 of them as pip packages, Presidio supplies the PII family, Llama Guard supplies model-based classification, and the engineering is choosing placement, cost, and failure policy per risk rather than picking a library.
**Follow-up trap:** *"So is a JSON schema check a guardrail?"* — yes, and insisting it isn't reveals you think guardrails means content moderation only. The schema check is the best kind: deterministic, sub-millisecond, testable. The trap is believing guards must be ML; the strong answer names the three families (deterministic, statistical, model-based) and orders them by cost.

### Q2 — Deterministic, statistical, or model-based validators: how do you choose for a given risk?
**Testing:** cost/coverage reasoning, not recall of product names.
**Answer:** Ascending cost, ascending coverage. Deterministic (regex, schema, checksums, canaries, blocklists) runs sub-millisecond in-process on everything: schema conformance, banned domains, well-formed identifiers, Luhn-validated card numbers. Statistical (Presidio-style pattern + context + optional NER) costs tens-to-hundreds of ms and covers format-variance in PII, tunable per entity via confidence thresholds. Model-based (Llama Guard-class, hundreds of ms, a full forward pass) covers semantics: novel jailbreaks, paraphrased toxicity, contextual PII. Rule: never pay tier-3 cost for a tier-1 guarantee, and always put a tier-1 prefilter in front of a tier-3 classifier so it only sees the residue.
**Follow-up trap:** *"Your PII regex misses a card number typed with spaces and unicode separators, and your statistical detector false-positives on order IDs. Fix it."* — layer them: regex for the high-precision well-formed cases, checksum validation where the format has one, context words to suppress the order-ID false positive, and accept the documented Presidio caveat that automated detection is not exhaustive, which is why the tool-boundary control (don't fetch card numbers into context at all) is the real answer.

### Q3 — Where do guardrails run, and why does placement matter?
**Testing:** architecture-level thinking; the chokepoint question.
**Answer:** Three places. In-app (in-process or sidecar) for anything needing request context: which tool results are untrusted, which user, which risk tier the action carries; deterministic and statistical guards live here. At a shared LLM gateway for org-wide policy and especially egress masking (Presidio's LiteLLM-proxy recipe exists so PII never reaches the provider). In the platform (Azure content filters, Bedrock Guardrails, OpenAI moderation) for always-on, zero-marginal-latency baseline coverage, with the caveat that platform guards are not configurable in the ways that matter and Bedrock's `ApplyGuardrail` API at least makes them callable building blocks. Layered beats one chokepoint because a gateway guard cannot see tool results or downstream actions, and its failure is a single total bypass.
**Follow-up trap:** *"Why not put everything at the gateway so you maintain it once?"* — because the highest-value guard is usually on the *consequence*, not the text: a jailbroken model with no refund tool cannot issue refunds. Gateway guards are policy consistency; app guards are risk specificity; tool gates are blast-radius control. "Once" optimizes the wrong variable.

### Q4 — Walk me through PII handling with reversibility. What can go wrong?
**Testing:** whether you've actually designed a redaction pipeline, including the failure modes.
**Answer:** Presidio's Analyzer detects spans (pattern + checksum + context + optional NER, ~80 entity types across 20-plus jurisdictions); the Anonymizer applies an operator. For reversibility the choices are keyed `encrypt`, or pseudonymization (`replace` with stable tokens like `PERSON_1`), which keeps referents consistent so the model can reason over the text. Pseudonymization creates a mapping that is itself PII, so: per-request map keyed by token (never span index), never logged, destroyed after render, re-hydration exactly once in the final render path, and output guards run on the model text *before* hydration. The classic de-anonymization result (Narayanan & Shmatikov, 2008) plus LLM-era style/context leakage means pseudonymized text is not anonymous text.
**Follow-up trap:** *"The model needs the real customer name to write a personalized email. Where do you hydrate?"* — only in the render path, after output guards, with a per-request map; the model itself works from pseudonyms plus a *template instruction* ("address the customer as <PERSON_1>'s display name"). If the model genuinely must see real values, scope the exposure: allow that entity type only for that tool/session, and then the output guard for that session skips that entity rather than blocking. The trap answer is "hydrate right after the model call and let the UI render" — that puts un-guarded PII in every downstream hop.

### Q5 — How does Llama Guard actually work, mechanically?
**Testing:** whether "we use Llama Guard" means you know the mechanism or just the name.
**Answer:** An 8B Llama-3.1 fine-tune (or 12B multimodal Llama Guard 4) that emits `safe` or `unsafe` plus violated categories S1-S14 (MLCommons taxonomy plus Code Interpreter Abuse). The same model classifies prompts and responses under different policies selected via the chat template, and input filtering versus output filtering is a real trade: input filtering catches harm before the model responds, output filtering lets the model attempt a safe answer and censors only the result; Meta recommends both. Scores come from the probability of the first generated token, thresholded by you. Numbers: F1 0.939 / FPR 0.040 on their English response benchmark vs Llama Guard 2 at 0.877 / 0.081 and GPT-4 zero-shot at 0.805 / 0.152; 8 languages; INT8 variant ~40% smaller for cheaper serving; deliberate training on *benign borderline* data to suppress false positives.
**Follow-up trap:** *"It's an LLM classifying jailbreaks. Can't you jailbreak the guard?"* — yes, and Meta's own model card says it may be susceptible to adversarial or prompt-injection attacks. That's why it is a layer, not a boundary: deterministic prefilters catch known attacks cheaply, the classifier catches novel ones probabilistically, and the tool-permission tiers are the deterministic backstop that a jailbroken model cannot talk its way past. Anyone claiming the classifier alone is the security boundary fails this question.

### Q6 — A guard errors mid-request. What happens?
**Testing:** fail-open vs fail-closed as a designed decision, and whether you know real platform behavior.
**Answer:** That's two events, not one. On *violation* you pass/fix/block/escalate per guard; on *failure* (error, timeout, 500 from the moderation API) the fail policy is a per-risk decision: PII scan for an internal summarizer fails open with an alarm; jailbreak classifier for a refund agent fails closed. The industry default is quiet fail-open because blocking on a dependency 500 looks like an outage, and Azure documents exactly this: if its content filter errors, the request completes *unfiltered*, with an error object in `content_filter_results` you are expected to monitor. The design answer: explicit `on_error` per guard, alerts on guard-error events (not just violations), and for fail-closed guards, a degraded-mode response that is honest rather than a generic 500.
**Follow-up trap:** *"Your jailbreak guard fails closed, moderation API has 99.9% uptime, so worst case you block 0.1% of traffic. Fine?"* — 0.1% of your traffic is still a lot of users, and outages are correlated (your dependency's bad deploy hits during your peak). The follow-up answer is redundancy with *divergent* implementations for fail-closed risks (platform filter plus app-side prefilter), plus circuit-breaking to a safer degraded mode, plus measuring guard-error rate as a first-class SLO. "Fine" is the failing answer.

### Q7 — Repair loops versus blocking: when do you re-ask the model?
**Testing:** whether you know the reask pattern and its costs.
**Answer:** Re-ask when the violation is a *format* defect and the fix is self-describing: schema failure, missing required field, validator feedback appended to the prompt (Guardrails AI's repair loop; NeMo's self-check flows). Cap retries (1-2), and on the last failure fall back to block or a template response, because a repair loop is a while-true over your most expensive dependency. Block when the violation is *semantic* and irreparable by the model itself: toxicity, PII leak, groundedness failure; re-asking "please don't leak the card number" just spends another token budget on a compromised context. Transform-and-continue when the fix is deterministic and safe: redact and proceed, strip the banned link and proceed.
**Follow-up trap:** *"Re-ask latency is two model calls on every failure. What's your budget?"* — the honest structure: guard latency must be sized against the *value of the request*, e.g. a few hundred ms of guards on a sub-second chatbot is 30-50% overhead, while on a 5-minute agent run it's noise; so synchronous model-based guards belong in slow, high-risk paths, and streaming paths use async scoring with retraction for what's retractable and pre-stream gating for what isn't (OpenAI's inline moderation returns scores only after the full output, not per-delta, which forces exactly this decision).

### Q8 — You run a public agent at 100 QPS. Every message through Llama Guard is too expensive. What do you do?
**Testing:** the economics of coverage; tiering under a budget.
**Answer:** Tier and sample. Layer 0: deterministic prefilters (signatures, encoding detection, known jailbreak corpora) on everything, sub-ms. Layer 1: run the classifier on *suspicion* (prefilter hit) and on *risk-tiers* (traffic with tool access or external effects always classified; read-only chat sampled at, say, 10-20% with the sample biased to new sessions). Layer 2: asynchronous scoring for the rest, score arrives post-render, and on a flag you retract the response and disable downstream effects for that turn. Then do the arithmetic out loud: an 8B classifier sidecar on vLLM serves hundreds of calls per second per GPU, so "too expensive" usually means "serialized in the hot path," not "the GPU can't keep up."
**Follow-up trap:** *"Sampling means some jailbreaks get through unsampled. Acceptable?"* — quantify what the sample is protecting: with 10% sampling you intercept ~10% of attempted jailbreaks *detection*, but your real containment is the tool tiers, so the classifier is a *detection and telemetry* layer, not the containment layer. The failing answer treats classifier coverage as the security boundary and promises 100% scanning without pricing it.

### Q9 — How do canary-based leak detection work, and where do they fail?
**Testing:** knowledge of a specific cheap technique and its bypass.
**Answer:** Generate a high-entropy random token per session (or per surface), embed it in the system prompt or tool results, and run a sub-ms substring scan for it on every text leaving the trust boundary: model output, tool-call arguments, log lines, summaries. A hit means content from inside the trust boundary leaked outward, which catches system-prompt exfiltration and some injection-exfiltration patterns regardless of *what* was leaked. Failure modes: paraphrase defeats it only partially (the canary must be copied verbatim to be useful to the attacker, which is why it works), but an attacker who can *strip* it or instruct the model to not echo it (or encode it) bypasses the scan; and it detects *that* a leak occurred, not *what* leaked or *where to*. So it's a tripwire, not a seal: pair it with egress allowlists and the permission backstop. Bedrock's Prompt Attack category explicitly covers prompt *leakage*, so platform guardrails name this risk class too.
**Follow-up trap:** *"The canary appeared in a tool result, not the final answer. Do you block?"* — yes, and that's the point of scanning every egress surface, not just the response: the leak already left your boundary once it reached the tool. But the triage differs: a canary in a *search query* the model constructed is an exfiltration-in-progress (block, alert, kill the session's tool access); a canary in a log line you wrote yourself is your own bug. The distinction is whether the flow was model-controlled.

### Q10 — Guardrails AI vs NeMo Guardrails vs platform filters: how do you pick?
**Testing:** framework knowledge at selection level, plus honesty about overlap.
**Answer:** Match the tool to the job. **Guardrails AI**: per-request validator composition with repair loops, 65-validators Hub as pip packages, `on_fail` actions per validator; right when your core need is output validation with self-correction, and note the 2026 packaging transition (hosted inferencing sunset, PyPI validators) if you were planning on its server. **NeMo Guardrails**: five rail types including dialog and retrieval rails, Colang flows; right when you want *conditional* guarding (fact-check only these intents) or conversation scripting, and you accept Colang as a second language in your codebase. **Platform filters**: Azure (4 categories x 4 severities, optional jailbreak/PII/protected-material, Prompt Shields), Bedrock (6 content categories, denied topics, word filters, PII block/mask, grounding checks, `ApplyGuardrail` callable standalone), OpenAI moderation (free, 13 categories, text+image). Use them as the always-on baseline and add app-side guards only for the gaps: custom policy, tool results, reversibility, things the platform can't express. The honest overlap point: for plain content harm on a single-provider app, platform filters alone are a complete answer and a second layer is cost, not safety.
**Follow-up trap:** *"We're multi-provider. One framework, or per-app?"* — the framework-agnostic answer is a thin internal guard interface (the 50-line shape) with providers behind it, because the *placement and policy* are yours regardless of framework, and vendor transitions (like the Guardrails AI 2026 change) then cost you a config, not an architecture. Picking one vendor's orchestration as your systemic boundary is the fragility the trap is testing.

### Q11 — Design the guard architecture for a regulated fintech agent that can read accounts, move money, and talk to customers.
**Testing:** principal-level synthesis, placement, ordering, budget, audit, measurement.
**Answer:** Start from a risk inventory, not a tool list. Risks: PII/PCI in transcripts and logs, regulated advice (investment advice = Bedrock's canonical denied-topic example), fraud/social-engineering of the agent, jailbreak-driven unauthorized transfers, hallucinated balances, and audit obligations. Then place guards by risk: (1) *tool boundary first*: the money-moving tool is tier-gated with approval for out-of-pattern transfers, and the accounts tool *projects* data so full card numbers never enter model context, prevention over detection. (2) *Input guards*: deterministic encoding/format prefilter, Presidio PII pseudonymization (map per-request, never logged), topic guard for regulated advice (deny-list plus a licensed-advisor escalation path, not a bare block), jailbreak prefilter + classifier for sessions with tool access. (3) *Output guards*: schema check on tool arguments before execution (the critical one: validate the transfer payload deterministically), PII scan pre-hydration, canary on every egress surface, groundedness check on any claim quoting account data. (4) *Platform layer*: provider content filters as baseline, deny investment-advice topics. (5) *Failure policy*: money-path guards fail closed; conversational guards fail open with alarms. (6) *Audit*: every guard decision logged with pseudonymized content, immutable for the regulated actions. (7) *Measurement*: FPR on benign traffic weekly, red-team suite in CI, score-drift monitors, guard-error SLO.
**Follow-up trap:** *"What's your latency budget and where does it break?"* — have real numbers: deterministic guards ~2-5 ms total, Presidio ~50-300 ms depending on engine and text length, classifier hundreds of ms. On a chat path with a 1.5-2 s model call, 300-500 ms of synchronous guards is 20-30% overhead, so the tiered answer: synchronous deterministic + statistical plus *schema-on-tool-args* (always, it's sub-ms and guards the money), classifier on suspicion and on money-path intents, async elsewhere. Stating a budget out loud is the pass; "we'd measure it" without a shape is the fail.

### Q12 — How do you measure guardrail efficacy without hurting UX?
**Testing:** whether you know the two-sided metric problem, and the over-blocking number.
**Answer:** Two corpora, two numbers, reported together. **Recall side**: a red-team suite (jailbreak corpus, PII-seeded transcripts, injection-through-tool-result cases) run in CI; report per-guard and per-category catch rate, and treat a regression like a test failure. **Precision side**: false-positive rate on *benign production traffic* (sampled, human-labeled or LLM-judged), because the product-destroying failure is over-blocking: XSTest (arXiv 2308.01263) exists precisely to measure exaggerated safety, and Meta trained Llama Guard 3 on benign borderline data specifically to push FPR down to 0.040 from Llama Guard 2's 0.081, which tells you even the vendor treats benign-FPR as the headline metric. Then watch drift: score distributions over time (a moderation model upgrade silently moves thresholds, OpenAI documents this), guard-error rate as an SLO, and the ratio of blocked-benign to blocked-malicious as the number you show the product team. Finally, shadow-mode rollouts for new guards: log-only for two weeks, measure what would have been blocked before letting it block.
**Follow-up trap:** *"Your red-team suite passes 100% but the suite is 6 months old. Are you safe?"* — no; the suite measures yesterday's attacks. Efficacy is a *rate of adaptation*, not a state: continuous red-teaming, canary tripwires for the novel stuff, and the containment posture (tool tiers) that holds when detection misses. Anyone letting "the suite is green" terminate the safety conversation fails the principal bar.

---

## Red flags that fail you

- "The platform handles it" with no inventory of *what* it handles (tool results? custom policy? its own documented fail-open?).
- Fail-open everywhere because blocking hurts UX, stated as a virtue.
- Regex-only PII detection, presented as sufficient.
- Guardrails as one layer/one chokepoint, usually "a middleware we added."
- Scanning user input but not tool results or retrieved chunks.
- No per-guard fail policy; no answer for "the moderation API 500s."
- Re-hydration of pseudonyms before output guards, or the pseudonym map persisted/logged.
- "Llama Guard can't be jailbroken because it's a safety model."
- No numbers: no latency budget, no FPR on benign traffic, no cost per guarded call.
- Treating the red-team suite as a completed state rather than a rate of adaptation.
- Picking a framework before writing the coverage matrix of risks x surfaces x layers.
- Blocked-content logs readable by everyone; guard logs not treated as PII-bearing.

---

## Cheat card

```
GUARDRAIL = deterministic validation + policy around a nondeterministic model
  4 VERBS: classify (topic/PII/jailbreak) · verify (schema/facts) ·
           transform (redact/mask) · route (pass/block/fix/escalate)
  every guard has TWO policies: on_violation AND on_error (per RISK, never global)

VALIDATOR FAMILIES (order by cost: run cheap first)
  deterministic  regex·schema·checksum·blocklist·canary   <1 ms   in-process
  statistical    Presidio: pattern+context+checksum+NER   ~50-300 ms
                 DE_PLZ base confidence 0.05 -> context words REQUIRED
  model-based    Llama Guard 3 8B / Guard 4 12B / omni-moderation  ~100-400 ms
                 = one model forward pass per guarded message

LLAMA GUARD 3: 14 categories S1-S14 (MLCommons + CodeInterpreterAbuse)
  8 languages · F1 0.939 / FPR 0.040 (vs LG2 0.877/0.081, GPT4 0.805/0.152)
  same model = prompt AND response policies via chat template
  score = FIRST-TOKEN probability, threshold yourself · INT8 ~40% smaller
  meta caveat: it's an LLM -> jailbreakable. It is a LAYER, not a boundary.

PII PIPELINE: Analyzer (detect) -> Anonymizer (operator)
  redact/mask = irreversible · hash/encrypt = keyed · replace = pseudonym
  pseudonym map: per-request · keyed by TOKEN (not span) · never logged ·
  destroyed after render · hydrate EXACTLY ONCE in the final render path
  output guards run BEFORE hydration · de-anonymization is real (Netflix 2008)
  Presidio: ~80 entities, 20+ jurisdictions (SSN 9d, UK_NHS 10d, Aadhaar 12d,
  card 12-19d + Luhn) · docs caveat: detection NOT exhaustive -> least privilege
  prevention beats detection: project columns at the TOOL boundary

PLACEMENT: app (context: tool results, risk tiers) · gateway (org policy,
  egress masking, Presidio+LiteLLM recipe) · platform (always-on baseline)
  Bedrock ApplyGuardrail = platform guards WITHOUT invoking the model
  layers beat chokepoints: gateway guard can't see tool results; 1 failure = total bypass
  best guard is often on the ACTION (tool tiers), not the text

PLATFORM FILTERS
  OpenAI moderation: FREE · omni-moderation-latest · 13 categories 0-1 scores
    text+image (<=20 MB) · covers tool-call args, NOT tool names/descriptions
    model upgrades silently -> recalibrate custom thresholds · stream scores post-output
  Azure: 4 harms (hate/sexual/violence/self-harm) x 4 severities (safe=annotate only)
    + jailbreak, PII, protected material, groundedness (streaming+regions),
    Prompt Shields (user + INDIRECT attacks in docs) · 400 on bad prompt,
    finish_reason=content_filter · FILTER ERROR => 200 UNFILTERED (fail-open, documented)
  Bedrock: 6 content categories incl Prompt Attack (jailbreak+injection+leakage) ·
    denied topics · word filters · PII block/mask + custom regex ·
    contextual grounding · automated reasoning checks · blocked content = PLAINTEXT in logs

FRAMEWORKS
  Guardrails AI: Guard().use(Validator, on_fail=...) · hub 65 validators, pip packages
    reask repair loop (cap retries) · hosted inferencing SUNSET Aug 25 2026
  NeMo Guardrails: 5 rail types (input/dialog/retrieval/execution/output) ·
    Colang flows · self check facts / hallucination · check jailbreak on input

ORCHESTRATION
  violation -> pass|fix(deterministic+safe)|re-ask(format defects, cap N)|block|escalate
  failure  -> per-risk fail-open(alarm) vs fail-closed(money/jailbreak paths)
  tiering: prefilter -> classifier on suspicion; sample low-risk traffic;
  async score + retraction for streams · schema-on-tool-args ALWAYS (sub-ms, guards money)

EFFICACY = 2 CORPORA, 2 NUMBERS, REPORTED TOGETHER
  red-team suite in CI (per-guard catch rate) · FPR on sampled BENIGN production
  traffic (the product-killer; XSTest arXiv 2308.01263 = exaggerated-safety test)
  monitor: score distribution drift · guard-error rate as SLO ·
  blocked-benign : blocked-malicious ratio · shadow mode (log-only) before enforce
```

## Sources

- [Guardrails AI — GitHub README](https://github.com/guardrails-ai/guardrails) — validators as PyPI packages, `on_fail` actions, re-ask/structured generation, Flask server, Guardrails Index (Feb 2025, 24 guardrails, 6 categories), July 2026 PyPI migration and hosted-inferencing sunset (Aug 25, 2026) — accessed 2026-09-06
- [Guardrails Hub](https://guardrailsai.com/hub) — 65 validators, categories, Presidio-backed Detect PII, Rebuff-backed injection detection, Llama Guard and ShieldGemma validators — accessed 2026-09-06
- [NVIDIA NeMo Guardrails — GitHub README](https://github.com/NVIDIA-NeMo/Guardrails) — 5 rail types, Colang 1.0/2.0, config.yml example (check jailbreak, mask sensitive data, self check facts/hallucination), release 0.23.0, Python 3.10-3.13, EMNLP 2023 — accessed 2026-09-06
- [Llama Guard 3 8B — model card (Hugging Face)](https://huggingface.co/meta-llama/Llama-Guard-3-8B) — 14 categories, 8 languages, F1/FPR tables vs Llama Guard 2 and GPT-4, first-token probability scoring, prompt vs response classification, tool-use training, INT8 ~40% smaller, XSTest result, benign-data curation — accessed 2026-09-06
- [Llama Guard 4 12B — model card (Hugging Face)](https://huggingface.co/meta-llama/Llama-Guard-4-12B) — 12B dense pruned from Llama 4 Scout, multimodal, single GPU, input vs output filtering trade-offs, 3:1 text:multimodal training ratio, classifier performance table — accessed 2026-09-06
- [Presidio — documentation](https://data-privacy-stack.github.io/presidio/) — analyzer/anonymizer architecture, recognizer types, operators incl. encryption and pseudonymization, no-guarantee warning, LiteLLM proxy PII-masking recipe, community transition — accessed 2026-09-06
- [Presidio — supported entities](https://data-privacy-stack.github.io/presidio/supported_entities/) — entity catalogue across 20+ jurisdictions, detection methods (pattern/checksum/context), DE_PLZ base confidence 0.05, medical NER recognizer — accessed 2026-09-06
- [OpenAI — Moderation guide](https://platform.openai.com/docs/guides/moderation) — omni-moderation-latest, free endpoint, 13 categories with scores, text+image (20 MB), inline Responses API moderation, tool-call argument coverage, streaming scores after full output, continuous model upgrades / threshold recalibration — accessed 2026-09-06
- [Microsoft — Content filtering for Azure OpenAI / Foundry Models](https://learn.microsoft.com/en-us/azure/ai-services/openai/concepts/content-filter) — 4 categories x 4 severities, annotate/block options, Prompt Shields (user + indirect attacks), groundedness (streaming, regions), PII, protected material, HTTP 400 / content_filter finish_reason, Scenario 6: filter error returns 200 unfiltered — accessed 2026-09-06
- [AWS — Amazon Bedrock Guardrails](https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails.html) — content filters (Hate/Insults/Sexual/Violence/Misconduct/Prompt Attack), denied topics, word filters, sensitive-information filters (block/mask, custom regex, probabilistic), contextual grounding, automated reasoning checks, ApplyGuardrail API, plaintext blocked content in invocation logs — accessed 2026-09-06
- [NeMo Guardrails: A Toolkit for Controllable and Safe LLM Applications with Programmable Rails (arXiv 2310.10501)](https://arxiv.org/abs/2310.10501) — the EMNLP 2023 paper introducing the rail architecture
- [Llama Guard: LLM-based Input-Output Safeguard for Human-AI Conversations (arXiv 2312.06674)](https://arxiv.org/abs/2312.06674) — the original Llama Guard paper, prompt/response policy design
- [XSTest: A Test Suite for Identifying Exaggerated Safety Behaviours in Large Language Models (arXiv 2308.01263)](https://arxiv.org/abs/2308.01263) — the benign-corpus false-positive methodology
- Narayanan & Shmatikov, "Robust De-anonymization of Large Sparse Datasets" (IEEE S&P 2008) — the classic sparse-data re-identification result behind the pseudonymization caveat

## Changelog
- 2026-09-06 — created
