# Tool Engineering: Schemas, Errors, Idempotency, Sandboxing

> **Track:** T07 Agentic AI · **Time:** 2.5h · **Prereqs:** `T07-agent-loop-from-scratch` · **Updated:** 2026-07-26
> **Module id:** `T07-tool-engineering` · **Tags:** sprint, core, tools
> **Lab:** none yet — see `labs/py/02-agent-loop/` for the pattern if you want to build one

## The 30-second version

A tool is a contract between a deterministic system and a non-deterministic one, which means the **description field is prompt engineering** and the JSON Schema is only the type-checking half of the spec. Four things dominate reliability, in this order: consolidate tools so each one maps to a task a human would recognise (`search_contacts`, not `list_contacts`); name and parameterise them so the model cannot be ambiguous (`user_id`, not `user`; namespaced prefixes; enums over free strings; examples over prose); truncate and shape results **at the tool boundary**, because a 200KB payload is the tool's bug and not the loop's; and return errors as actionable observations so a failure becomes something the model routes around instead of an exception that discards a nine-step run. On top of that sit three safety properties that are not optional in production: idempotency keys on every mutating tool, explicit risk tiers gating which tools need approval, and a real sandbox — microVM, not container — for anything executing untrusted code. And know the scaling wall: tool selection degrades measurably past roughly 10 to 20 tools, with Berkeley Function Calling data showing accuracy collapsing from 43% to 2% as a tool set went from 4 to 51, so the fix is fewer better tools plus retrieval-based discovery, not a bigger prompt.

## Why this gets asked

Because tools are where agent quality actually comes from, and almost everyone underinvests in them. The candidate who has only built demos talks about the agent loop and the model choice. The candidate who has shipped talks about the time a tool returned 200KB of JSON and blew the context window on step 3, or the retried `create_ticket` that produced four tickets, or the day they added the twelfth tool and accuracy on the existing eleven got worse. The interviewer is probing for a specific mental shift: **tools are not API wrappers.** Wrapping your existing REST endpoints one-to-one is the single most common mistake in this space, because your API was designed for a client with cheap memory and perfect recall, and the model has neither. At staff level they will also probe the blast radius question — what stops the agent from `rm -rf`-ing something, and how you know.

---

## Lineage: past → present → future

**What came before.** In 2022, "tool use" meant text parsing. **ReAct** (Yao et al., 2022) had the model emit `Action: search[query]` as prose and you regexed it out, which failed constantly: the model would emit `Action: search("query")`, or add commentary inside the brackets, or nest a bracket. **Toolformer** (Meta, Feb 2023) trained the model to emit API calls itself, which worked but required fine-tuning per tool set. **ChatGPT Plugins** (Mar 2023) tried to skip schema design entirely by handing the model your OpenAPI spec and a natural-language manifest. It died fast, and the specific pain is worth naming because it's the lesson of this module: a full OpenAPI spec is enormous, written for human developers, exposes dozens of endpoints with overlapping purposes and opaque identifiers, and the model hallucinated endpoints and parameters at a rate that made the feature unusable. **OpenAI function calling** (June 2023) fixed the parsing problem by making tool calls first-class structured API objects with JSON Schema, and every provider followed. That removed an entire bug class but exposed the real one: the model now emitted syntactically valid calls to the wrong tool with the wrong parameters. **Gorilla** (Patil et al., May 2023) and API-Bank were the first serious attempts to measure that, and the Berkeley Function Calling Leaderboard grew out of it. **MCP** (Anthropic, Nov 2024) standardised transport and discovery so tools became portable across clients.

**Where it stands now.** Three things are consensus. First, **the description field is the highest-leverage lever available**, and it is prompt engineering rather than documentation — Anthropic reports that precise refinements to tool descriptions alone were what got Claude Sonnet 3.5 to state-of-the-art on SWE-bench Verified. Second, **fewer, better-consolidated tools beat more tools**, because tool definitions consume context and overlapping tools cause selection errors; the guidance is explicitly to build a few tools targeting high-impact workflows rather than mirroring your API surface. Third, **truncation belongs in the tool**; Claude Code caps tool responses at 25,000 tokens by default, and the recommended pattern is pagination plus filtering plus range selection with sensible defaults, and a truncation message that *steers* the model toward a narrower query. The scaling wall is now well quantified: MCP tool definitions for a five-server setup (GitHub 35 tools ≈ 26K tokens, Slack 11 ≈ 21K, Sentry 5 ≈ 3K, Grafana 5 ≈ 3K, Splunk 2 ≈ 2K) come to 58 tools and ≈55K tokens *before the conversation starts*; Jira alone is ≈17K; Anthropic measured 134K tokens of tool definitions internally before optimising. The **live disagreements** are real. (a) *Tools-as-JSON-calls versus tools-as-code*: Anthropic's Programmatic Tool Calling and Cloudflare's Code Mode argue the model should write Python that calls your tools in a sandbox so intermediate results never enter context, with measured average token use dropping 43,588 → 27,297 (37%) on complex research tasks; the counter-argument is that you have now made arbitrary code execution part of your control flow. (b) *Static tool sets versus dynamic discovery*: the Tool Search Tool approach defers loading and discovers on demand (≈500 tokens upfront, ≈8.7K total versus ≈77K, an 85% reduction) at the cost of an extra search round-trip. (c) *Whether MCP's risk annotations mean anything*, since they are advisory hints a server asserts about itself with no enforcement.

**Where it's heading.** **High confidence: progressive tool disclosure becomes the default for anything above ~20 tools.** Retrieval or search over a tool index, rather than a flat list in the system prompt, is now supported natively (Anthropic's Tool Search Tool, GA-track since the Nov 2025 beta) and the accuracy data is strong — internal MCP evals improved from 49% to 74% on Opus 4 and 79.5% to 88.1% on Opus 4.5 with Tool Search enabled. **Medium confidence: examples become as standard as schemas.** `input_examples` on a tool definition improved complex parameter handling from 72% to 90% in Anthropic's testing, which is a bigger delta than most model upgrades, and the argument that JSON Schema cannot express usage conventions is unanswerable. **Medium confidence: risk annotations become a real governance vocabulary.** MCP's `readOnlyHint` / `destructiveHint` / `idempotentHint` / `openWorldHint` (shipped in the 2025-03-26 spec revision) are hints, but control planes are starting to treat them as policy inputs, and the useful part is that the *defaults are pessimistic* — an unannotated tool is assumed destructive, non-idempotent, and open-world. **Speculative: code execution replaces individual tool calls as the default calling convention** for multi-tool workflows. The token numbers are extraordinary (workflows reported dropping from 150,000 to 2,000 tokens, ~98.7%) and the sandboxing story is maturing, but treat "everything becomes code mode" as a direction of travel, not settled practice.

---

## Mental model

**A tool is a job description for a new hire who has amnesia, cannot ask clarifying questions, and reads only what you wrote in the description.**

```
        ┌─────────────────────── THE TOOL BOUNDARY ────────────────────────┐
        │                                                                  │
 model ─┤ NAME        namespaced, verb_noun, unambiguous                    │
        │ DESCRIPTION ← PROMPT. what it's for, when NOT to use it,          │
        │               vocabulary, return shape, cost hints                │
        │ SCHEMA      enums > strings · user_id > user · flat > nested      │
        │ EXAMPLES    1-5 input_examples: conventions schema can't express  │
        ├──────────────────────────────────────────────────────────────────┤
        │ ── EXECUTE ──  auth as the USER, not the service                  │
        │                risk tier gate → approve / deny / run              │
        │                idempotency key if it mutates                      │
        │                sandbox if it's untrusted code                     │
        ├──────────────────────────────────────────────────────────────────┤
        │ RESULT      truncate HERE (not in the loop) · semantic ids >      │
        │             UUIDs · concise|detailed · steer on truncation        │
        │ ERROR       an OBSERVATION with the fix in it, never an exception │
        └──────────────────────────────────────────────────────────────────┘

   THE ASYMMETRY THAT EXPLAINS EVERYTHING:
     traditional client   → cheap memory, perfect recall, reads docs once
     model                → paid context, no memory, re-reads your description
                            every single turn
   ⇒ list_contacts() returning 5,000 rows is correct for a program
     and a bug for an agent.  Ship search_contacts(query) instead.
```

The corollary is the sentence to remember: **your REST API is not your tool surface.** One-to-one wrapping is the default mistake, and it is a mistake because the two consumers have opposite cost models.

---

## How it actually works

### 1. Choose which tools to build — consolidation beats coverage

Design tools around the *task*, not the endpoint. Three canonical rewrites:

| Instead of | Ship | Why |
|---|---|---|
| `list_users`, `list_events`, `create_event` | `schedule_event(...)` | finds availability and books in one call; three inference passes become one |
| `read_logs` | `search_logs(query, ...)` | returns matching lines plus context, not the file |
| `get_customer_by_id`, `list_transactions`, `list_notes` | `get_customer_context(id)` | one call assembles what the model actually needed |

Each consolidation does two things at once: it removes tool definitions from context, and it moves computation *out of the model's context and into your code* — the loop, the filtering, the joining. That's strictly better, because your code is deterministic and free and the model's version is neither.

Test: for every tool, can you name the human task it corresponds to? `list_contacts` fails that test. `search_contacts` and `message_contact` pass.

### 2. Naming and namespacing

- **`verb_noun`, imperative.** `search_orders`, `cancel_subscription`. Not `orders`, not `handle_order`.
- **Namespace by service and then by resource.** `asana_search` / `jira_search`; `asana_projects_search` / `asana_users_search`. Anthropic reports that the choice between prefix- and suffix-based namespacing has **non-trivial** effects on tool-use evals, varies by model, and should be chosen by measurement rather than taste.
- **Avoid near-identical names.** The most common failures are wrong tool selection and wrong parameters, and the named example is `notification-send-user` vs `notification-send-channel`. If two names differ by one word, the model will confuse them; either merge them behind one tool with a `target_type` enum, or rename so they differ structurally.
- **Node/tool names leak** into traces, logs, and (for LangGraph) checkpoint namespaces. Renaming later is not free.

### 3. The description is a prompt

Write it the way you'd brief a new hire: state the implicit context you'd otherwise assume. Specialised query syntax, domain vocabulary, relationships between resources, and — the part people skip — **when not to use this tool.**

```python
from langchain.tools import tool

@tool
def search_logs(
    query: str,
    service: str,
    since_minutes: int = 60,
    max_lines: int = 50,
) -> str:
    """Search application logs for lines matching a query.

    Use this to investigate errors, latency spikes, or specific request IDs.
    Do NOT use this to fetch a whole log file; there is no such tool by design.
    Prefer several narrow searches over one broad one.

    query: a substring or a `key=value` filter. Supported keys: request_id,
      user_id, status, level. Combine with spaces (implicit AND).
      Examples: "timeout", "request_id=req_8812", "level=error status=503".
    service: exact service name, e.g. "checkout-api". Use list_services if unsure.
    since_minutes: lookback window. Max 1440. Narrow this before widening `max_lines`.
    max_lines: hard cap on returned lines (default 50, max 200). Results are
      truncated with a marker; narrow the query rather than raising this.

    Returns newest-first lines as "<iso8601> <level> <message>". Empty result
    means no matches in the window, not an error.
    """
```

Every clause there is doing work: the *when not to* prevents a request for a nonexistent `read_logs`; the query grammar prevents malformed filters; "prefer several narrow searches" steers toward token-efficient behaviour; the return-shape description lets downstream code (or the model's own parsing) be correct; "empty means no matches, not an error" prevents the model from retrying a successful call three times.

**Real evidence this matters at the margin:** when Anthropic shipped Claude's web search tool, the model was needlessly appending `2025` to the `query` parameter, biasing results and degrading performance. The fix was a description change. That's the level of detail that moves numbers.

### 4. Parameter design that reduces model error

| Do | Don't | Why |
|---|---|---|
| `user_id: str` | `user: str` | `user` is ambiguous — id? name? email? The model guesses and guesses inconsistently. |
| `status: Literal["pending","shipped","delivered"]` | `status: str` | enums eliminate a whole error class and are enforced by the provider |
| flat parameters | deeply nested objects | valid JSON does not imply correct usage; nesting multiplies the ways to be wrong |
| `since: str  # ISO 8601 date, e.g. 2026-07-26` | `since: str` | format ambiguity is a top source of malformed calls |
| explicit `max_results: int = 20` | unbounded | gives the model a lever and you a default |
| `response_format: Literal["concise","detailed"]` | one fixed shape | lets the model pay for verbosity only when it needs ids |
| `input_examples` for anything nested | schema alone | 72% → 90% on complex parameter handling in Anthropic's testing |
| required params genuinely required | everything optional | "all optional" pushes the decision onto the model |

**Semantic identifiers beat opaque ones.** Anthropic found that resolving arbitrary alphanumeric UUIDs to semantically meaningful names — or even a 0-indexed scheme — **significantly improves retrieval precision by reducing hallucinations**. Models handle `checkout-api` better than `a3f9c1e2-...`. When downstream calls genuinely need the technical id, expose both via `response_format`: `"detailed"` includes ids for chaining (`search_user(name="jane")` → `send_message(id=12345)`), `"concise"` omits them. In Anthropic's Slack example that difference was 206 tokens versus 72 — roughly one third.

**`input_examples` earn their tokens on ambiguous schemas.** JSON Schema says `due_date` is a string; it cannot say whether that means `2024-11-06`, `Nov 6, 2024`, or an ISO timestamp, nor whether `reporter.id` is a UUID or `USR-12345`, nor which optional groups correlate. Three examples — full, partial, minimal — teach all of it. Guidance: 1–5 per tool, realistic data (`"San Francisco"`, not `"string"`), and only where the schema leaves genuine ambiguity.

### 5. Truncation and shaping at the boundary

**The rule: a tool that could return 200KB must return the useful 2KB, plus a pointer.** This belongs in the tool, not the loop, for three reasons — the tool knows what's relevant, doing it in the loop means you already paid to serialise and transport the payload, and it is the highest-leverage single fix available in agent engineering.

Four mechanisms, all with sensible defaults: **pagination**, **range selection**, **filtering**, **truncation**. Claude Code's default cap is 25,000 tokens per tool response.

Truncation must **steer**, not just cut:

```python
LIMIT = 8_000   # characters, ≈2K tokens

def shape(rows: list[dict], query: str, response_format: str = "concise") -> str:
    keep = ["timestamp", "level", "service", "message"] if response_format == "concise" \
           else None                                            # detailed = all fields
    body = render(rows, keep)
    if len(body) <= LIMIT:
        return body
    shown = count_rendered(body[:LIMIT])
    return (body[:LIMIT] +
            f"\n\n[TRUNCATED: showing {shown} of {len(rows)} matches. "
            f"Narrow the query (add level=, status=, or request_id=) or reduce "
            f"since_minutes, rather than increasing max_lines.]")
```

Note what the truncation message contains: the counts, and **the specific next action**. "Output truncated" teaches the model nothing; naming the parameters to narrow teaches it the efficient strategy.

**Drop low-signal fields.** Return `name`, `file_type`, `image_url`. Not `uuid`, `mime_type`, `256px_image_url`, `etag`, `_links`. Prioritise contextual relevance over flexibility.

**Response format matters and there is no universal winner.** XML, JSON, and Markdown measurably differ in eval performance because models are next-token predictors and do better on shapes resembling their training data. Pick by evaluation, per task.

### 6. Errors as observations

Every path returns a readable string. Nothing raises into the loop.

```python
def execute(tools: dict, name: str, args: dict) -> str:
    if name not in tools:
        close = difflib.get_close_matches(name, tools, n=3)
        return (f"Error: no tool named '{name}'. "
                + (f"Did you mean: {', '.join(close)}? " if close else "")
                + f"Available: {', '.join(sorted(tools))}")
    try:
        validated = tools[name].args_schema(**args)          # pydantic
    except ValidationError as e:
        return (f"Error: invalid arguments for '{name}'.\n{compact(e)}\n"
                f"Expected schema: {tools[name].args_schema.model_json_schema()}\n"
                f"Example of a valid call: {tools[name].example_call}")
    try:
        return shape(tools[name].run(validated), limit=8_000)
    except RateLimited as e:
        return f"Error: rate limited, retry after {e.retry_after}s. Do something else first."
    except NotFound as e:
        return (f"Error: {e.resource} '{e.identifier}' not found. "
                f"Verify the id with search_{e.resource}s first.")
    except PermissionDenied as e:
        return (f"Error: not permitted — {e.reason}. Do not retry; "
                f"tell the user what approval is needed.")
    except Exception as e:                                    # deliberately broad
        log.exception("tool %s failed", name)                  # you still need the trace
        return f"Error: '{name}' failed — {type(e).__name__}: {e}. Try a different approach."
```

Two things distinguish this from a naive `try/except`:

- **The error text is prompt-engineered.** It states what went wrong *and* the corrective action, with an example where relevant. An opaque code or a raw traceback wastes a turn. Anthropic's guidance is explicit that error responses should communicate specific, actionable improvements.
- **The distinction between the tool's dependency failing and your harness being broken.** A 503 from a search backend is an observation the model can route around. A `KeyError` in your dispatch code is a bug the model cannot fix, and swallowing it ships an agent that looks merely stupid. Return the former; log and (in dev) crash on the latter.

A subtle one: **do not make "no results" an error.** `search()` returning nothing is a successful call with an empty result, and the description should say so, or you get the classic no-progress loop where the model retries an identical query three times expecting a different answer.

### 7. Idempotency on mutating tools

Retries happen — transport retries, per-node `RetryPolicy` retries, human-approval re-runs, and (in LangGraph) node re-execution on resume, since resume restarts a node from its first line. Every one of those can execute a mutating tool twice.

```python
@tool
def create_ticket(title: str, body: str, priority: str, idempotency_key: str) -> str:
    """Create a support ticket.

    idempotency_key: a stable identifier for THIS logical ticket. Reuse the same
      key when retrying; a repeat returns the existing ticket instead of a
      duplicate. Derive it from the request you are handling, never randomly.
    """
```

Two design choices, and the second is better:

- **Model-supplied key.** Simple, and wrong under retry: the model regenerates a different key, so you get duplicates anyway.
- **Harness-supplied key.** The runtime derives it deterministically from execution identity — `f"{thread_id}:{checkpoint_id}:create_ticket"` in LangGraph, or `f"{run_id}:{step}:{tool_name}:{hash(args)}"` generally — and injects it. Identical across re-runs by construction, and the model can't get it wrong. This is the right answer.

Server side, store `(key → response)` **atomically**: `INSERT ... ON CONFLICT DO NOTHING` and check the affected-row count. Read-then-write races and double-processes. TTL must exceed your maximum retry window, which for a human approval gate may be days. And the hard case worth naming: if the first request is still in flight when the retry arrives, either return 409 and let the caller back off, or block on a lock keyed by the idempotency key with a short timeout.

Where you can, prefer **naturally idempotent** operations instead: `upsert_by_natural_key` over `insert`, `set_status(id, "closed")` over `close(id)`, PUT semantics over POST.

### 8. Risk tiers and permissions

Classify every tool, and let the tier drive behaviour rather than reviewing each call by hand:

| Tier | Examples | Auto-retry | Approval | Audit |
|---|---|---|---|---|
| `read_only` | search, get, list | yes | no | sampled |
| `write_reversible` | create draft, add comment, tag | yes, **with idempotency key** | no | every call |
| `write_external` | send email, post to Slack, call a partner API | key required, no blind retry | policy-dependent | every call |
| `financial` | refund, charge, transfer, issue credit | **never** blind | **always** | every call, immutable log |
| `destructive` | delete, drop, revoke, force-push | **never** | **always**, with a typed confirmation | every call, immutable log |

Enforce at the boundary, not in the prompt. "Do not delete anything without asking" in a system prompt is a suggestion; a dispatcher that refuses to execute a `destructive` tool without an approval token is a control.

```python
RISK = {"search_logs": "read_only", "create_ticket": "write_reversible",
        "send_email": "write_external", "issue_refund": "financial",
        "delete_index": "destructive"}
NEEDS_APPROVAL = {"financial", "destructive"}

def dispatch(name, args, approvals: set[str]):
    tier = RISK.get(name, "destructive")          # UNKNOWN = MOST DANGEROUS
    if tier in NEEDS_APPROVAL and name not in approvals:
        raise ApprovalRequired(name, tier, args)  # → interrupt() / HITL
    ...
```

`RISK.get(name, "destructive")` is the load-bearing line: **default to the most dangerous tier for unclassified tools**, so adding a tool without classifying it fails closed rather than open.

**MCP tool annotations** are the emerging standard vocabulary for this, shipped in the **2025-03-26** spec revision:

| Annotation | Meaning | Default |
|---|---|---|
| `readOnlyHint` | does not modify its environment | `false` |
| `destructiveHint` | may perform destructive updates | `true` |
| `idempotentHint` | repeat calls with same args have no additional effect | `false` |
| `openWorldHint` | may interact with external entities | `true` |

The defaults are deliberately pessimistic, so an unannotated tool is assumed destructive, non-idempotent, and open-world — exactly the fail-closed posture above. **But they are hints a server asserts about itself, with no enforcement.** A malicious or careless server can claim `readOnlyHint: true` on a tool that deletes your data. Use them to *reduce friction on tools you trust* (skip confirmation for genuinely read-only calls), never as your security boundary.

**Also enforce least privilege on credentials.** A tool should act with the *user's* authority, not the service's. An agent holding a service account that can read every tenant's data is a confused-deputy vulnerability waiting for a prompt injection, and prompt injection through tool *results* is the live threat: untrusted content enters context as an observation and instructs the model. The mitigation is not "detect injections" — it is that the tools available at that moment cannot do the damage the injection asks for.

### 9. Sandboxing untrusted execution

If a tool executes model-generated code, or processes untrusted input in a way that could become code execution, you need real isolation. The 2026 position:

| Isolation | Boundary | Verdict for LLM-generated code |
|---|---|---|
| `subprocess` / `exec()` in-process | none | **never** |
| Container (Docker) | shared host kernel | **insufficient** — one kernel bug is a host escape |
| gVisor | user-space kernel, syscall interception | acceptable; Modal's multi-tenant sandboxes run on it |
| microVM (Firecracker, Kata) | hardware virtualisation, own kernel | **the production-safe answer** |

The performance objection is gone. Firecracker boots in **~125ms** with **under 5 MiB** memory overhead per VM and supports up to **150 VMs per second per host**; E2B (Firecracker-based) reports cold starts around **150ms** and Daytona around **90ms**. Cold start in the 90–200ms range is acceptable for essentially every agent use case, which means choosing a weaker boundary for speed is no longer a defensible trade.

Isolation is necessary and not sufficient. The full checklist:

1. **microVM or gVisor**, one per session, destroyed after.
2. **No credentials inside.** No cloud metadata endpoint (`169.254.169.254`), no env secrets, no mounted service-account token. If the sandbox needs data, pass it in; if it needs to write, have it return a result your trusted code applies.
3. **Network egress denied by default**, then allowlisted per destination. Unrestricted egress turns any sandbox into an exfiltration channel regardless of how well it's isolated.
4. **Resource caps**: CPU, memory, wall clock, disk, process count. A fork bomb should kill the VM, not the host.
5. **Filesystem**: read-only root, small writable tmpfs, no host bind mounts.
6. **Non-root, seccomp/AppArmor**, no `CAP_SYS_ADMIN`, no `--privileged`.
7. **Log the code, not just the result.** When something goes wrong you need to know what ran.

The GPU caveat, since it comes up in ML interviews: if the sandbox needs to run inference or fine-tune, Modal is currently the only serious option among managed sandbox providers that gives a sandbox a GPU.

### 10. The scaling wall: tool selection past ~20 tools

Two independent measurements of the same effect:

- **Berkeley Function Calling Leaderboard**: accuracy on calendar scheduling dropped from **43% to 2%** as the available tool set grew from **4 to 51** tools across multiple domains.
- **RAG-MCP** (arXiv 2505.03275, May 2025): baseline tool selection accuracy **13.62%** with a large tool set; retrieval-based selection exposing only the relevant subset reached **43.13%** — more than triple — while cutting prompt tokens by **over 50%**.

Practitioner reports put measurable degradation starting around **10–15** tools, with 20+ noticeably worse than a focused set of 5–8. And the context cost compounds: 58 tools across five MCP servers is ≈55K tokens before the first user message; Anthropic measured 134K internally pre-optimisation.

Six fixes, cheapest first:

1. **Delete tools.** The subtraction principle. Most tool sets have redundant or never-selected tools; instrument selection frequency and remove the tail.
2. **Consolidate** (§1). Five tools become two that map to real tasks.
3. **Improve names and descriptions**, and disambiguate near-identical pairs. Free, and it addresses selection directly.
4. **Namespace** by service and resource so the model can eliminate whole groups.
5. **Gate by state/permission.** Bind only the tools valid for this user and this phase. A read-only user never sees `issue_refund`; a triage phase never sees `settle`.
6. **Retrieval or search over a tool index.** Native support exists: mark tools `defer_loading: true` and expose a tool-search tool. Measured effect — ≈500 tokens loaded upfront instead of ≈72K, total context ≈8.7K versus ≈77K (**85% reduction**), with MCP eval accuracy improving **49% → 74%** (Opus 4) and **79.5% → 88.1%** (Opus 4.5). It does not break prompt caching, because deferred tools were never in the cached prefix. Guidance on when: tool definitions over 10K tokens, observed selection problems, multi-server MCP setups, 10+ tools. Not worth it under 10 tools or when every tool is used every session.
7. **Subagents with scoped tool sets** — a research subagent with 4 tools and a billing subagent with 4 tools each select better than one agent with 8, at the cost of routing and handoff. This is the *second* thing to try, not the first.

And the heavier option: **push the orchestration into code.** Programmatic Tool Calling has the model write Python that calls tools in a sandbox, so intermediate results never enter context — measured 43,588 → 27,297 average tokens (37%), internal knowledge retrieval 25.6% → 28.5%, GAIA 46.5% → 51.2%, and in the worked example 200KB of expense line items collapsed to 1KB of results. Reported end-to-end reductions from treating MCP servers as code APIs reach 150,000 → 2,000 tokens (~98.7%). The cost is that arbitrary code execution is now part of your control flow, which puts you squarely back in §9.

### 11. Testing tools independently of the agent

**Three layers, and only the third one needs a model.**

**Layer 1 — the tool is ordinary software.** Unit test it with no LLM in sight: happy path, empty result, not-found, rate limit, permission denied, and a payload large enough to trigger truncation with an assertion on the *steering message*. Property-test the idempotency key: calling twice with the same key produces one side effect and identical responses. This layer is fast, deterministic, and catches most bugs.

```python
def test_truncation_steers():
    out = search_logs.invoke({"query": "x", "service": "s", "max_lines": 200})
    assert "[TRUNCATED" in out
    assert "Narrow the query" in out          # the message must be ACTIONABLE
    assert len(out) < 9_000

def test_idempotent_create():
    a = create_ticket.invoke({**args, "idempotency_key": "k1"})
    b = create_ticket.invoke({**args, "idempotency_key": "k1"})
    assert a == b and fake_db.ticket_count() == 1
```

**Layer 2 — schema contract tests, no model.** Assert the description is non-empty and above a minimum length; every parameter has a description; free-form strings that should be enums aren't; `input_examples` validate against the schema; names match `^[a-z][a-z0-9_]*$` and are unique; **every mutating tool has a risk tier and an idempotency key**; no two tool names are within an edit distance you consider confusable. These are cheap CI checks that catch the entire class of "someone added a tool without a description."

**Layer 3 — evals with an agent, which is where you measure selection.** Build a harness of realistic tasks with verifiable outcomes and a simple `while` loop per task. What makes this work:

- **Realistic, multi-step tasks.** "Customer 9182 reported being charged three times for one purchase attempt. Find all relevant log entries and determine whether other customers were affected" — not "search the payment logs for `purchase_complete`." Weak tasks that name the tool and its arguments measure nothing.
- **Verifiers that aren't brittle.** String match where possible, LLM-as-judge where not, and never reject a correct answer over formatting.
- **Metrics beyond accuracy:** number of tool calls, total tokens, per-call latency, tool error rate by tool, and which tools were selected. Redundant calls point at bad pagination defaults; invalid-parameter errors point at bad descriptions or missing examples.
- **A held-out test set.** Anthropic's own reporting is that held-out sets revealed gains beyond hand-written "expert" tool implementations, and that iterating on descriptions against an eval is what produced most of their guidance. Without held-out data you are overfitting your descriptions to your fixtures.
- **Ask the agent.** Have evaluation agents emit reasoning and feedback blocks *before* their tool calls, then read the transcripts. The documented caveat is the interesting part: what agents *omit* is often more informative than what they say, so read the raw tool calls too, not just the stated reasoning.

---

## Build it from scratch

A tool registry that makes the right thing the default: validation, truncation, risk tiers, harness-supplied idempotency keys, and errors as observations.

```python
# untested sketch
import difflib, hashlib, json, logging
from dataclasses import dataclass, field
from typing import Any, Callable, Literal
from pydantic import BaseModel, ValidationError

log = logging.getLogger(__name__)
Tier = Literal["read_only", "write_reversible", "write_external", "financial", "destructive"]
NEEDS_APPROVAL: set[Tier] = {"financial", "destructive"}


class ApprovalRequired(Exception):
    def __init__(self, name, tier, args):
        super().__init__(f"{name} ({tier}) requires approval")
        self.name, self.tier, self.args = name, tier, args


@dataclass
class Tool:
    name: str
    description: str
    args_model: type[BaseModel]
    fn: Callable[..., Any]
    tier: Tier = "destructive"                  # fail CLOSED if unspecified
    limit: int = 8_000
    examples: list[dict] = field(default_factory=list)
    needs_idem_key: bool = False

    def schema(self) -> dict:
        s = {"name": self.name, "description": self.description,
             "input_schema": self.args_model.model_json_schema()}
        if self.examples:
            s["input_examples"] = self.examples
        return s


class Registry:
    def __init__(self, tools: list[Tool]):
        self.tools = {t.name: t for t in tools}
        self._validate_contracts()

    def _validate_contracts(self):
        """Layer-2 checks. Run in CI too, not just at startup."""
        for t in self.tools.values():
            assert len(t.description) > 120, f"{t.name}: description too thin to steer"
            props = t.args_model.model_json_schema().get("properties", {})
            for p, spec in props.items():
                assert spec.get("description"), f"{t.name}.{p}: undocumented parameter"
            if t.tier != "read_only":
                assert t.needs_idem_key, f"{t.name}: mutating tool without idempotency key"
        names = list(self.tools)
        for i, a in enumerate(names):
            for b in names[i + 1:]:
                assert difflib.SequenceMatcher(None, a, b).ratio() < 0.90, \
                    f"confusable tool names: {a} / {b}"

    def schemas(self) -> list[dict]:
        return [t.schema() for t in self.tools.values()]

    def execute(self, name: str, args: dict, *, run_id: str, step: int,
                approvals: set[str] | None = None) -> str:
        """ALWAYS returns a string the model can read. Never raises to the loop."""
        approvals = approvals or set()

        tool = self.tools.get(name)
        if tool is None:
            near = difflib.get_close_matches(name, self.tools, n=3)
            return (f"Error: no tool named '{name}'."
                    + (f" Did you mean: {', '.join(near)}?" if near else "")
                    + f" Available: {', '.join(sorted(self.tools))}")

        if tool.tier in NEEDS_APPROVAL and name not in approvals:
            raise ApprovalRequired(name, tool.tier, args)   # caller → interrupt()/HITL

        try:
            validated = tool.args_model(**args)
        except ValidationError as e:
            msg = "; ".join(f"{'.'.join(map(str, x['loc']))}: {x['msg']}" for x in e.errors())
            out = f"Error: invalid arguments for '{name}' — {msg}."
            if tool.examples:
                out += f" Example of a valid call: {json.dumps(tool.examples[0])}"
            return out

        kwargs = validated.model_dump()
        if tool.needs_idem_key:
            # DETERMINISTIC in execution identity: identical across every re-run.
            digest = hashlib.sha256(
                json.dumps(kwargs, sort_keys=True, default=str).encode()).hexdigest()[:12]
            kwargs["idempotency_key"] = f"{run_id}:{step}:{name}:{digest}"

        try:
            raw = tool.fn(**kwargs)
        except Exception as e:
            log.exception("tool %s failed", name)           # keep the traceback for YOU
            return (f"Error: '{name}' failed — {type(e).__name__}: {e}. "
                    f"Try a different approach or a different tool.")

        return self._shape(raw, tool)

    @staticmethod
    def _shape(raw: Any, tool: Tool) -> str:
        body = raw if isinstance(raw, str) else json.dumps(raw, default=str)
        if not body:
            return "No results. This is not an error; the query matched nothing."
        if len(body) <= tool.limit:
            return body
        return (body[:tool.limit] +
                f"\n\n[TRUNCATED at {tool.limit} chars of {len(body)}. Narrow your "
                f"query or use pagination/filter parameters rather than re-requesting.]")
```

`labs/py/03-tool-engineering/` builds this incrementally against a fake backend: the registry and contract checks, truncation with a steering assertion, error taxonomy, the idempotency property test, the risk-tier gate raising `ApprovalRequired`, and finally a small eval harness that measures selection accuracy at 5, 12, and 25 tools so you can watch the wall arrive on your own data.

---

## How it's done in production

**LangChain / LangGraph.** `@tool` derives the schema from type hints and the description from the docstring, so **the docstring is your prompt** — a one-line docstring is a one-line prompt. Use Pydantic `args_schema` with `Field(description=...)` when you need per-parameter text or validators. `ToolNode` executes calls from the last `AIMessage` and returns `ToolMessage`s; by default it catches tool exceptions and returns them as tool messages, which is the right behaviour, but know it's happening or you'll wonder why your tests never see the raise. Tools can access graph state via injected arguments and return a `Command` to update state and route. `langchain` 1.2.0 (Dec 2025) added an `extras` attribute on tools for provider-specific parameters, which is how you reach Anthropic's tool search and programmatic tool calling from `create_agent`.

**MCP.** Standard transport and discovery; server-side tools become portable across clients. Two things to carry into an interview: annotations (`readOnlyHint`, `destructiveHint`, `idempotentHint`, `openWorldHint`, since the 2025-03-26 revision) are **advisory hints with no enforcement**, and the ecosystem's tool-description quality is poor enough that surveys find a high proportion of published MCP tools with at least one quality issue. Adopting a third-party MCP server means adopting its context cost, its descriptions, and its trust posture.

**Provider-side features worth naming** (Anthropic, beta header `advanced-tool-use-2025-11-20`): `defer_loading: true` plus a tool-search tool for discovery; `allowed_callers: ["code_execution_20250825"]` to opt a tool into programmatic calling; `input_examples` on the tool definition. These are the productised versions of §10 and §4.

### What breaks at scale

| Symptom | Cause | Fix |
|---|---|---|
| Context blows up on step 2–3 | tool returns the whole payload | truncate + filter **in the tool**; cap ~2K tokens or 25K default |
| Model calls the same tool with identical args repeatedly | "no results" returned as an error, or truncation with no guidance | say "empty is not an error" in the description; actionable truncation message |
| Frequent invalid-parameter errors | free-form strings where enums belong; ambiguous names; no examples | `Literal[...]`, `user_id` not `user`, add `input_examples` |
| Wrong tool chosen between two similar ones | near-identical names (`notification-send-user` / `-channel`) | merge behind one tool with an enum, or rename structurally |
| Accuracy dropped after adding tools 12–20 | selection degrades with tool count (BFCL 43% → 2% at 4 → 51) | delete, consolidate, namespace, gate by state, then tool search / RAG |
| ~55K–134K tokens gone before the first user message | many MCP servers loaded eagerly | `defer_loading` + tool search (≈85% reduction) |
| Duplicate tickets / double charges | non-idempotent mutating tool retried, or node re-run on resume | harness-supplied idempotency key; upsert semantics |
| Duplicate side effect only after a human approval | resume re-runs the node from its first line | move the mutation after the interrupt / into its own node |
| Model deleted something in prod | no risk tier, or tier enforced only in the prompt | tier gate in the dispatcher; unknown ⇒ `destructive` |
| Agent read another tenant's data | tool used a service credential, not the user's | per-user auth; least privilege; assume prompt injection |
| Sandbox escape / data exfiltration | Docker treated as a security boundary; open egress | microVM (Firecracker/Kata) or gVisor; deny egress by default; no creds inside |
| Prompt injection via a tool result | untrusted content entering context as an observation | scope the tools so the injection's ask is impossible; don't rely on detection |
| Tool works in tests, fails with the agent | tested the function, never tested selection | layer-3 evals on realistic multi-step tasks with a held-out set |
| Descriptions improved, evals didn't | overfitted to the training tasks | held-out test set; report both |

**Instrument per tool**, not just per run: call count, error rate by error class, p50/p99 latency, tokens returned, truncation rate, and selection frequency. Selection frequency is the one people skip and it's the one that tells you which tools to delete.

---

## Tradeoffs & when NOT to use it

- **Don't build a tool where a parameter would do.** Two tools that differ only in a filter should be one tool with an enum. Every extra tool costs context and selection accuracy.
- **Don't consolidate to the point of a god tool.** `do_customer_thing(action: str, payload: dict)` defeats schema validation, defeats enums, defeats risk tiering, and moves all the ambiguity into a free-form dict. The sweet spot is a tool per task a human would name.
- **Tool search is not free.** It adds a search round-trip before invocation, and under 10 tools — or when every tool is used every session — it's pure latency. The guidance thresholds are >10K tokens of definitions, observed selection problems, or 10+ tools.
- **`input_examples` cost tokens on every turn.** Worth it for nested schemas, domain conventions, and disambiguating similar tools (`create_ticket` vs `create_incident`). Not worth it for a single-parameter tool with an obvious URL or email.
- **Programmatic tool calling / code mode is a real security decision.** The token savings are large and the accuracy gains are real, but you have made arbitrary code execution part of your control flow. If you can't stand up a microVM sandbox with denied egress and no credentials, don't adopt it. Also skip it for simple single-tool lookups, and when the model genuinely should reason about intermediate results.
- **Sandboxing has a floor cost.** ~90–200ms cold start and orchestration complexity. If your tool doesn't execute untrusted code, don't buy it — but if it does, a container is not the answer and the latency argument for using one no longer holds.
- **`response_format: concise|detailed` adds a decision the model can get wrong.** Two shapes are usually enough. A GraphQL-style field selector gives maximum flexibility and maximum ways to produce a malformed request.
- **MCP annotations are not a security boundary.** They are self-asserted hints. Use them to reduce friction on tools you already trust; never to decide whether something is safe.
- **Third-party MCP servers are a context and trust liability.** Adopting a 35-tool server means adopting ~26K tokens, someone else's descriptions, and someone else's idea of what `destructive` means. Wrap and curate rather than mounting wholesale.

---

## Interview questions

### Q1 — Why does a tool's description matter so much?
**Testing:** whether you see the description as documentation or as prompt.
**Answer:** It's loaded into the model's context every turn and it's the primary thing steering selection and parameter construction — it *is* prompt engineering. Write it like a brief for a new hire: what the tool is for, when **not** to use it, the query grammar, the domain vocabulary, the return shape, and cost hints ("prefer several narrow searches"). The evidence is that precise description refinements alone took Claude Sonnet 3.5 to state-of-the-art on SWE-bench Verified, and that Claude's web search tool was needlessly appending `2025` to queries until the description was fixed.
**Follow-up trap:** *"Isn't the JSON Schema enough?"* — no. Schema says what's structurally valid; it can't express conventions. It can't say whether `due_date` is `2024-11-06` or an ISO timestamp, whether `reporter.id` is a UUID or `USR-12345`, or which optional groups correlate. That's what `input_examples` are for: Anthropic measured 72% → 90% on complex parameter handling from adding 1–5 realistic examples.

### Q2 — Design a tool for searching customer orders. Talk me through your choices.
**Answer:** `search_orders` (verb_noun, namespaced if there are sibling services). Parameters: `customer_id: str` — not `customer` — with a documented format; `status: Literal["pending","shipped","delivered"]` as an enum; `since: str` documented as ISO 8601 with an example; `max_results: int = 20`; `response_format: Literal["concise","detailed"] = "concise"`. Returns newest-first, only high-signal fields (`id`, `total`, `status`, `created_at`), and truncates at ~2K tokens with a message naming which parameters to narrow. Description states the query grammar, that an empty result is not an error, and that there is deliberately no `list_all_orders`.
**Follow-up trap:** *"Why not just wrap `GET /orders`?"* — because your REST API was designed for a client with cheap memory and perfect recall, and the model has paid context and no memory. A one-to-one wrapper leaks pagination cursors, `_links`, `etag`, and UUIDs into context, offers no search affordance, and forces brute-force reading. Consolidate around the task: `search_orders`, not `list_orders` plus `get_order`.

### Q3 — A tool returns 200KB of JSON. What do you do and where?
**Answer:** Fix it in the **tool**, not the loop. Filter to high-signal fields, paginate, add range selection, and truncate with a sensible default — Claude Code's default cap is 25,000 tokens per tool response. Do it in the tool because the tool knows what's relevant, and because doing it in the loop means you already paid to serialise and transport 200KB.
**Follow-up trap:** *"What must the truncation message contain?"* — the counts and the **specific corrective action**: "showing 50 of 4,812 matches; narrow with `level=` or `request_id=`, or reduce `since_minutes`, rather than raising `max_lines`." "Output truncated" teaches the model nothing and it will re-request the same thing with a bigger limit. Truncation is a steering opportunity.

### Q4 — A tool throws. What does the model see?
**Answer:** A string describing the failure and the fix. Never an exception into the loop — propagating one discards a nine-step run over a transient 503. Give errors a taxonomy: unknown tool (list the available ones plus a did-you-mean), validation error (compact message plus the schema plus a valid example), rate limit (with `retry_after` and "do something else first"), not found (with "verify the id via `search_x` first"), permission denied ("do not retry; tell the user what approval is needed"), and a broad catch-all.
**Follow-up trap:** *"Always catch everything?"* — no. Distinguish "the tool's dependency failed" (return to the model) from "my harness has a bug" (log the traceback and fail loudly, because the model cannot fix your `KeyError`, and swallowing it ships an agent that looks merely stupid). And don't make "no results" an error — that's a successful call with an empty result, and misclassifying it produces the classic loop where the model retries an identical query three times.

### Q5 — How do you make a mutating tool safe to retry?
**Answer:** Idempotency keys, with the key supplied by the **harness**, not the model. Derive it deterministically from execution identity — `f"{thread_id}:{checkpoint_id}:{tool}"` in LangGraph, or `f"{run_id}:{step}:{tool}:{hash(args)}"` — so it's identical across re-runs by construction. Server side, store `(key → response)` atomically with `INSERT ... ON CONFLICT DO NOTHING` and check the affected-row count; read-then-write races. TTL must exceed the maximum retry window. Better still, prefer naturally idempotent operations: upsert by natural key, `set_status(id, "closed")` rather than `close(id)`, PUT rather than POST.
**Follow-up trap:** *"Why not let the model generate the key?"* — because on retry it generates a *different* key and you get duplicates anyway, which is the exact failure the key was meant to prevent. Second trap: *"What if the first request is still in flight when the retry arrives?"* — that's the hard case; either return 409 and let the caller back off, or take a lock keyed by the idempotency key with a short timeout.

### Q6 — Your agent's accuracy dropped after you added the twelfth tool. Diagnose and fix.
**Testing:** whether you know the scaling wall exists and is measured.
**Answer:** Tool selection degrades with tool count. BFCL data shows calendar-scheduling accuracy falling from 43% to 2% as the tool set went from 4 to 51, and practitioner reports put measurable degradation at 10–15 tools. Fixes cheapest first: **delete** tools nothing selects (instrument selection frequency); **consolidate** so each tool maps to a human task; **improve descriptions** and disambiguate near-identical names; **namespace** by service and resource; **gate by state and permission** so only valid tools are bound; then **retrieval over a tool index** — mark tools `defer_loading: true` and expose a tool-search tool, which measured ≈500 tokens upfront versus ≈72K, total context ≈8.7K versus ≈77K (85% reduction), with MCP eval accuracy going 49% → 74% on Opus 4 and 79.5% → 88.1% on Opus 4.5.
**Follow-up trap:** *"Isn't the answer multi-agent?"* — that's the *second* thing to try, not the first. Subagents with scoped tool sets do select better, but you pay routing errors, context handoff loss, harder debugging, and more latency. Exhaust deletion, consolidation, descriptions, and tool search first. And note the honest caveat: tool search adds a round-trip and is not worth it under ~10 tools or when every tool is used every session.

### Q7 — Walk me through the risk tiers and how you enforce them.
**Answer:** Five tiers: `read_only` (auto-retry, no approval, sampled audit), `write_reversible` (retry *with* an idempotency key), `write_external` (key required, no blind retry, policy-dependent approval), `financial` (never blind, always approval, immutable audit), `destructive` (never blind, always approval with typed confirmation, immutable audit). Enforce in the **dispatcher**, not the prompt — "don't delete without asking" is a suggestion; a dispatcher that refuses a `destructive` call without an approval token is a control. And default unknown tools to `destructive` so adding one without classifying it fails closed.
**Follow-up trap:** *"MCP has annotations for this — just use them?"* — know them (`readOnlyHint` default `false`, `destructiveHint` default `true`, `idempotentHint` default `false`, `openWorldHint` default `true`, shipped in the 2025-03-26 revision) and note the defaults are pessimistic, which is right. But they are **hints the server asserts about itself with no enforcement**. A careless or malicious server can claim `readOnlyHint: true` on a tool that deletes data. Use them to reduce friction on tools you already trust; never as the security boundary.

### Q8 — A tool runs model-generated Python. How do you sandbox it?
**Answer:** microVM, not container. Containers share the host kernel, so one kernel bug is a host escape; for LLM-generated code the production-safe layer is Firecracker or Kata, with gVisor as an acceptable middle (Modal runs its multi-tenant sandboxes on it). The performance excuse is gone: Firecracker boots in ~125ms with under 5 MiB overhead per VM and up to 150 VMs/sec/host; E2B reports ~150ms cold starts and Daytona ~90ms. Then: one sandbox per session, destroyed after; **no credentials inside** and no cloud metadata endpoint reachable; **egress denied by default** with a per-destination allowlist; CPU/memory/wall-clock/disk/process caps; read-only root plus a small tmpfs, no host mounts; non-root with seccomp; and log the code, not just the result.
**Follow-up trap:** *"You've isolated it — are you safe?"* — no. Isolation without **egress control** still gives you an exfiltration channel, and a mounted service-account token makes the isolation irrelevant. Also the prompt-injection angle: untrusted content arriving in a tool *result* enters context as an observation and can instruct the model. You don't defend that by detecting injections; you defend it by ensuring the tools available at that moment cannot do what the injection asks. That's why risk tiering and per-user least-privilege credentials are part of the sandbox story, not separate from it.

### Q9 — How do you test tools without an LLM in the loop?
**Answer:** Three layers, and two need no model. **Layer 1**: the tool is ordinary software — unit test happy path, empty result, not-found, rate limit, permission denied, and a payload big enough to trigger truncation with an assertion that the truncation message is *actionable*; property-test that two calls with the same idempotency key produce one side effect and identical responses. **Layer 2**: schema contract tests in CI — every tool has a substantial description, every parameter has a description, strings that should be enums are enums, examples validate against the schema, names match a pattern and are unique and not confusable, and every mutating tool has a tier and an idempotency key. **Layer 3** needs a model, and that's where you measure selection.
**Follow-up trap:** *"What does layer 3 look like?"* — realistic multi-step tasks with verifiable outcomes, run through a simple `while` loop per task, one agent per task. Tasks must not name the tool: "customer 9182 was charged three times, find the log entries and determine who else was affected," not "search the payment logs for `purchase_complete`." Metrics beyond accuracy: tool-call count, tokens, latency, error rate by tool, and which tools were selected. And a **held-out** test set, or you're overfitting descriptions to fixtures — Anthropic reports held-out sets revealed gains beyond hand-written expert implementations.

### Q10 — What's the single most common mistake you see in tool design?
**Answer:** One-to-one wrapping of an existing API. Your API was built for a client with cheap memory and perfect recall; the model has paid context and no memory. So `list_contacts` returning 5,000 rows is correct software and a broken tool — the agent brute-force reads it token by token. Ship `search_contacts` and `message_contact` instead. The related version is exposing every endpoint as a tool, which blows context and degrades selection simultaneously.
**Follow-up trap:** *"Give me three concrete consolidations."* — `list_users` + `list_events` + `create_event` → `schedule_event`; `read_logs` → `search_logs` returning matching lines plus context; `get_customer_by_id` + `list_transactions` + `list_notes` → `get_customer_context`. Each removes tool definitions from context *and* moves the loop/filter/join out of the model's reasoning into deterministic code, which is strictly better on cost, latency, and correctness.

### Q11 — Should tool results return UUIDs?
**Answer:** Usually not in the default shape. Anthropic found that resolving arbitrary alphanumeric UUIDs to semantically meaningful names — or even a 0-indexed scheme — **significantly improves retrieval precision by reducing hallucinations**. Models handle `checkout-api` better than `a3f9c1e2-…`. Strip low-signal technical fields generally: return `name`, `file_type`, `image_url`, not `uuid`, `mime_type`, `256px_image_url`.
**Follow-up trap:** *"But the next tool call needs the real id."* — expose both via `response_format`: `"detailed"` includes ids so `search_user(name="jane")` → `send_message(id=12345)` works, `"concise"` omits them. In Anthropic's Slack example the difference was 206 tokens versus 72, roughly a third. Alternatively resolve names to ids server-side inside the tool, so the model never handles an id at all — which is better when you can do it.

### Q12 — Make the case for and against having the model write code that calls your tools.
**Testing:** whether you can hold both sides of a live disagreement.
**Answer:** **For:** intermediate results never enter context. In the worked budget-compliance example, 2,000+ expense line items (200KB) collapsed to ~1KB of results; measured average token use dropped 43,588 → 27,297 (37%) on complex research tasks; internal knowledge retrieval went 25.6% → 28.5% and GAIA 46.5% → 51.2%; and orchestrating 20 calls in one code block eliminates 19 inference round-trips. Reported end-to-end reductions from treating MCP servers as code APIs reach 150,000 → 2,000 tokens. Loops, conditionals, and joins are also more reliable as explicit code than as natural-language reasoning. **Against:** you have made arbitrary code execution part of your control flow, so you now own everything in the sandboxing answer — microVM, denied egress, no credentials, resource caps. It also hides the intermediate results from the model, which is exactly wrong when the model *should* reason over them, and it's pure overhead for a single lookup.
**Follow-up trap:** *"So which would you ship?"* — start with the cheapest fix for your actual bottleneck. Context bloat from *definitions* → tool search. Context bloat from *results* → truncation at the boundary first, code execution only if truncation genuinely can't work because you need aggregates over large data. Parameter errors → `input_examples`. Reaching for code mode before fixing your truncation is solving the expensive problem first.

### Q13 — You inherit an agent with 40 tools from six MCP servers and it's slow and inaccurate. First week?
**Answer:** Measure before changing. Instrument per tool: selection frequency, error rate by class, tokens returned, truncation rate, latency. Then in order: (1) delete the tail nothing selects; (2) find the confusable name pairs and merge or rename; (3) fix descriptions on the highest-error tools and add `input_examples` where invalid-parameter errors cluster; (4) put truncation in whichever tools return the biggest payloads; (5) `defer_loading` the servers whose tools are rarely used and expose a tool-search tool, keeping the 3–5 most-used loaded; (6) build a held-out eval before step 3 so you can prove any of it worked. Expect the context arithmetic to be the shocking part — 58 tools across five servers is ≈55K tokens before the first user message, and Anthropic measured 134K internally before optimising.
**Follow-up trap:** *"Which single change usually gives the biggest win?"* — truncation at the tool boundary, because context growth costs you on *every subsequent turn* and it's the cheapest to implement. Definition-side savings from tool search are larger in absolute tokens (≈85% reduction) but need an eval to verify you haven't hurt selection, so it's the bigger win and the later change.

### Q14 — Your agent runs inside LangGraph with a human approval gate. What does that change about tool design?
**Answer:** Two things. First, **the node re-runs from its first line on every resume**, so a mutating tool called before the `interrupt()` executes once per resume attempt — a reviewer who bounces a request three times produces three side effects. Design tools so the mutation lives in its own node after the decision is durable, and give it a harness-supplied idempotency key derived from `(thread_id, checkpoint_id)` with a TTL longer than the maximum approval window, which may be days. Second, the approval gate is where risk tiers become real: the dispatcher raises `ApprovalRequired` for `financial` and `destructive` tiers, which the graph turns into an `interrupt()` carrying the tool name, arguments, and a human-readable summary.
**Follow-up trap:** *"Does LangGraph give you exactly-once tool execution?"* — no, and saying yes fails. It documents at-least-once and instructs you to make side effects idempotent; a task that starts but fails to complete re-runs on resume. Exactly-once is a property of the downstream system or of an idempotency layer you own, not of the orchestrator.

---

## Red flags that fail you

- Describing tools as "wrappers around our API."
- Treating the description as documentation rather than as prompt.
- No truncation story, or truncation in the loop instead of the tool.
- Letting a tool exception propagate and kill the run.
- Truncating without telling the model what to do about it.
- "Add retries" with no mention of idempotency.
- Letting the model generate the idempotency key.
- Enforcing permissions in the system prompt instead of the dispatcher.
- Defaulting unclassified tools to safe rather than dangerous.
- Calling Docker a security boundary for LLM-generated code.
- Sandboxing but leaving egress open or credentials mounted.
- Treating MCP annotations as enforcement rather than self-asserted hints.
- Not knowing that tool selection degrades with tool count.
- Reaching for multi-agent before deleting unused tools.
- Testing tool functions but never testing tool *selection*.
- No held-out eval set.

---

## Cheat card

```
CORE ASYMMETRY  traditional client: cheap memory, perfect recall
                model: PAID context, no memory, re-reads your description every turn
  ⇒ your REST API is NOT your tool surface. 1:1 wrapping is THE default mistake.

CONSOLIDATE (task, not endpoint)
  list_users+list_events+create_event → schedule_event
  read_logs                          → search_logs (matches + context)
  get_customer_by_id+txns+notes      → get_customer_context
  test: can you name the HUMAN task? list_contacts fails. search_contacts passes.

NAME  verb_noun · namespace by service THEN resource (asana_projects_search)
  prefix vs suffix namespacing has NON-TRIVIAL eval effects — measure, don't guess
  top failures = WRONG TOOL + WRONG PARAMS (notification-send-user vs -channel)

DESCRIPTION = PROMPT (not docs)
  what it's for · WHEN NOT TO USE IT · query grammar · vocabulary · return shape
  "prefer several narrow searches" · "empty result is NOT an error"
  evidence: description-only refinements → SOTA on SWE-bench Verified
            web search tool was appending "2025" until the description was fixed

PARAMS  user_id > user · Literal[...] > str · flat > nested · document formats + example
  max_results with a default · response_format: concise|detailed (206 → 72 tokens ≈ 1/3)
  SEMANTIC ids > UUIDs (measurably fewer hallucinations); expose ids only in "detailed"
  input_examples 1-5, realistic, full/partial/minimal → 72% → 90% on complex params

TRUNCATE AT THE TOOL (highest-leverage single fix)
  pagination + range + filter + truncate, all with sensible defaults
  Claude Code default cap: 25,000 tokens per tool response
  truncation message MUST STEER: counts + WHICH PARAM TO NARROW
  drop low-signal fields (uuid, mime_type, etag, _links, 256px_image_url)
  response shape (XML/JSON/MD) measurably matters — choose by eval

ERRORS = OBSERVATIONS, never exceptions into the loop
  unknown tool → did-you-mean + list · validation → compact msg + schema + example
  429 → retry_after + "do something else first" · 404 → "verify id via search_x"
  403 → "do NOT retry; tell the user what approval is needed"
  dependency failed → return to model.  YOUR bug (KeyError) → log + fail loudly.
  "no results" is SUCCESS, not an error (else infinite identical retries)

IDEMPOTENCY  HARNESS supplies the key, never the model (model regenerates on retry)
  f"{thread_id}:{checkpoint_id}:{tool}"  /  f"{run_id}:{step}:{tool}:{hash(args)}"
  server: INSERT ... ON CONFLICT DO NOTHING + check rowcount (read-then-write RACES)
  TTL > max retry window (days, if a human approval gate)
  prefer naturally idempotent: upsert > insert, set_status > close, PUT > POST

RISK TIERS (enforce in the DISPATCHER, not the prompt)
  read_only · write_reversible · write_external · financial · destructive
  RISK.get(name, "destructive")  ← unknown = MOST DANGEROUS. fail closed.
  MCP annotations (spec rev 2025-03-26), defaults are PESSIMISTIC:
    readOnlyHint=false · destructiveHint=TRUE · idempotentHint=false · openWorldHint=TRUE
  they are SELF-ASSERTED HINTS. NOT enforcement. never your security boundary.
  auth as the USER, not the service (confused deputy + prompt injection)

SANDBOX untrusted code
  in-process exec  → never       container (shared kernel) → INSUFFICIENT
  gVisor (Modal)   → acceptable  microVM Firecracker/Kata  → PRODUCTION ANSWER
  Firecracker ~125ms boot · <5 MiB/VM · up to 150 VMs/sec/host
  E2B ~150ms · Daytona ~90ms → the latency excuse is gone
  + NO creds/metadata inside · EGRESS DENIED by default · cpu/mem/wall/disk/proc caps
  + read-only root + tmpfs · non-root + seccomp · LOG THE CODE
  isolation without egress control = exfiltration channel

SCALING WALL  degradation starts ~10-15 tools; 20+ clearly worse than 5-8
  BFCL: 43% → 2% as tools went 4 → 51
  RAG-MCP (arXiv 2505.03275): 13.62% → 43.13% selection, >50% fewer prompt tokens
  context cost: 58 tools / 5 MCP servers ≈ 55K tokens BEFORE turn 1 (Jira alone ≈17K)
                Anthropic measured 134K tokens of tool defs pre-optimisation
  FIXES, cheapest first:
    1 DELETE (instrument selection frequency)   2 consolidate   3 fix names+descriptions
    4 namespace   5 gate by state/permission    6 tool search / RAG over tools
    7 subagents with scoped tool sets  ← SECOND resort, not first
  Tool Search: defer_loading:true + search tool · ~500 tok upfront vs ~72K
    total ~8.7K vs ~77K = 85% cut · Opus 4 49%→74% · Opus 4.5 79.5%→88.1%
    does NOT break prompt caching · use when >10K tok defs / 10+ tools / selection issues
  Programmatic Tool Calling: 43,588 → 27,297 tok (37%) · 200KB → 1KB in-example
    knowledge retrieval 25.6%→28.5% · GAIA 46.5%→51.2% · code-as-MCP 150K → 2K (~98.7%)
    COST: arbitrary code execution is now in your control flow → see SANDBOX

TESTING  L1 unit (no LLM): happy/empty/404/429/403 + truncation msg is ACTIONABLE
             + property test: same idem key ⇒ 1 side effect, identical response
         L2 contract in CI (no LLM): desc length, per-param descs, enums, examples
             validate, names unique + not confusable, every mutating tool has tier + key
         L3 evals (LLM): realistic MULTI-STEP tasks that don't name the tool
             metrics: accuracy + #calls + tokens + latency + error rate + WHICH tools
             HELD-OUT set or you're overfitting descriptions to fixtures
             read raw transcripts — what agents OMIT beats what they say
```

## Sources

- [Anthropic — Writing effective tools for agents, with agents](https://www.anthropic.com/engineering/writing-tools-for-agents) — consolidation, namespacing (prefix vs suffix effects), semantic ids over UUIDs, `concise`/`detailed` (206 → 72 tokens), 25,000-token response cap, actionable error responses, descriptions as prompt engineering, SWE-bench Verified result, evaluation methodology and held-out sets; accessed 2026-07-26
- [Anthropic — Introducing advanced tool use](https://www.anthropic.com/engineering/advanced-tool-use) — MCP tool-definition token costs (58 tools ≈55K, Jira ≈17K, 134K internal), Tool Search Tool (≈500 vs ≈72K, 85% cut, Opus 4 49→74%, Opus 4.5 79.5→88.1%), Programmatic Tool Calling (43,588→27,297, GAIA 46.5→51.2%), Tool Use Examples (72→90%), `defer_loading` / `allowed_callers` / `input_examples`; accessed 2026-07-26
- [Anthropic — Code execution with MCP](https://www.anthropic.com/engineering/code-execution-with-mcp) — treating MCP servers as code APIs; the 150K → 2K token framing; accessed 2026-07-26
- [RAG-MCP: Mitigating Prompt Bloat in LLM Tool Selection via Retrieval-Augmented Generation (arXiv 2505.03275)](https://arxiv.org/abs/2505.03275) — 13.62% → 43.13% selection accuracy, >50% prompt-token reduction; accessed 2026-07-26
- [MCP blog — Tool Annotations as Risk Vocabulary: What Hints Can and Can't Do](https://blog.modelcontextprotocol.io/posts/2026-03-16-tool-annotations/) — the four hints, their pessimistic defaults, 2025-03-26 spec revision, and why they aren't enforcement; accessed 2026-07-26
- [Northflank — How to sandbox AI agents in 2026: microVMs, gVisor & isolation strategies](https://northflank.com/blog/how-to-sandbox-ai-agents) — containers insufficient for LLM-generated code, Firecracker ~125ms / <5 MiB / 150 VMs/sec, E2B ~150ms, Daytona ~90ms, Modal on gVisor; accessed 2026-07-26
- [TianPan — The Over-Tooled Agent Problem](https://tianpan.co/blog/2026-04-19-over-tooled-agent-problem) and [The Tool Selection Problem](https://tianpan.co/blog/2026-04-09-tool-selection-problem-agent-tool-routing-at-scale) — degradation at 10–15 tools, BFCL 43% → 2% at 4 → 51 tools; accessed 2026-07-26
- [ReAct: Synergizing Reasoning and Acting in Language Models (arXiv 2210.03629)](https://arxiv.org/abs/2210.03629) — the text-parsing origin; accessed 2026-07-26
- [Gorilla: Large Language Model Connected with Massive APIs (arXiv 2305.15334)](https://arxiv.org/abs/2305.15334) — early measurement of tool-selection error; accessed 2026-07-26
- [LangChain Python changelog](https://docs.langchain.com/oss/python/releases/changelog) — `langchain` 1.2.0 tool `extras` for provider-specific tool parameters (Anthropic programmatic tool calling, tool search); accessed 2026-07-26
- [LangGraph — Interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts) — node re-runs from the top on resume; side effects before `interrupt()` must be idempotent; accessed 2026-07-26

## Changelog
- 2026-07-26 — created
