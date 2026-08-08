# Authoring MCP Servers for Your Own Codebase & Tools

> **Track:** T28 AI-Assisted Architecture (Claude) · **Time:** 2.5h · **Prereqs:** none · **Updated:** 2026-08-01
> **Module id:** `T28-mcp-authoring` · **Tags:** mcp

## The 30-second version

Writing an MCP server for your own codebase is an interface-design problem wearing a protocol costume, and the decision that dominates every other one is tool granularity: too many thin tools (`list_files`, `read_file`, `parse_frontmatter`, `write_file`) burns the agent's step budget assembling primitives you already had, and too few fat tools (one `manage_curriculum(action, payload)` god-tool) collapses composability and forces the model to guess an internal action vocabulary from a single opaque schema. The fix is workflow-shaped tools: name and shape each one around a task a caller actually wants done, not around a database operation you happen to expose. Two numbers anchor why this matters at all: independent 2026 benchmarks show tool-selection accuracy falling from roughly 19/20 at 20 tools to complete failure past 100, and a plain model picking from a large pooled catalogue scored 13.62% in one stress test — so a server with the wrong tool count is broken before a single call happens, regardless of how good any individual tool's schema is. The rest of authoring is mechanical once granularity is right: write schemas and error strings for a model that cannot see your code, make every mutating tool idempotent or offer `dry_run`, keep secrets on the server side, never in a tool argument, and test trigger accuracy and task success as two separate questions. Skip MCP entirely for a single in-process call nothing outside your own process will ever reach; that case is `T07-mcp-deep-dive`'s territory, not this module's.

## Why this gets asked

Because "I built an MCP server" and "I designed a tool interface an agent can actually use" are different claims, and almost every candidate who has done the former has not done the latter deliberately. The interviewer has personally watched an agent burn six of its ten allotted steps calling `get_project_id`, then `get_task_list_for_project`, then `filter_tasks_by_status`, because someone exposed their ORM instead of a workflow — and they have also watched the opposite, a single 40-parameter `do_everything` tool that the model calls with the wrong shape every third try because there was one schema for twelve different intents. They want to know if you think about tool design as UX for a non-human reader, or if you think a working `tools/call` handler is the finish line.

---

## Lineage: past → present → future

**What came before.** Before you could expose your own codebase to an agent at all, the two options were a bespoke plugin manifest (ChatGPT plugins, March 2023, dead within a year because every host wanted its own manifest shape) or a hand-rolled function-calling loop where "your tools" meant a Python dict of callables passed straight to the model provider's API, covered in `T07-tool-engineering`. Both worked for one codebase talking to one agent runtime. The pain that MCP fixes for *authoring* specifically is narrower than the protocol's general pitch: without a standard shape, every internal tool you wrote for one agent had to be rewritten, with a different schema dialect, the moment a second agent runtime (a teammate's IDE, a CI bot, a different model host) needed the same capability.

**Where it stands now.** FastMCP is reported to power roughly 70% of MCP servers in the wild ([KDnuggets, accessed 2026-08-01](https://www.kdnuggets.com/fastmcp-the-pythonic-way-to-build-mcp-servers-and-clients)), which means the authoring question in practice is "what do I put in `@mcp.tool`," not "how do I hand-roll JSON-RPC." Anthropic's own guidance, *Writing effective tools for agents* ([Anthropic Engineering, accessed 2026-08-01](https://www.anthropic.com/engineering/writing-tools-for-agents)), reframes the entire discipline around one sentence: you are not writing an API for another program, you are writing an interface for an agent that reads text and has no other way to know what your code does. The live disagreement is exactly how coarse to go — Anthropic's own examples namespace tools under a service prefix (`asana_search`, `jira_search`) and separately ship both full API-coverage tools and hand-curated workflow tools for the same server, which is itself an admission that neither granularity wins outright. The over-tooling failure is now measured, not anecdotal: Speakeasy's benchmark data shows large models scoring 19/20 correct tool selections at a 20-tool catalogue and failing completely by 107 tools ([How Too Many MCPs Break Your AI Agent in 2026, accessed 2026-08-01](https://albato.com/blog/publications/embedded-mcp-context-bloat-hallucinations)), and a controlled stress test of an unfiltered pooled catalogue put accuracy at 13.62% ([Adding More MCP Tools Made My AI Agent Dumber, Towards AI, accessed 2026-08-01](https://pub.towardsai.net/adding-more-mcp-tools-made-my-ai-agent-dumber-accuracy-collapses-past-20-8e754d09bee4)). GitHub Copilot's own fix — cutting from 40 tools to 13 — bought a 400ms latency drop and a 2-5 point accuracy gain on the same tasks, which is the production-side confirmation that fewer, better-named tools beat more, thinner ones.

**Where it's heading.** High confidence: progressive disclosure — a server exposing `list_capabilities`/`get_tool`/`invoke_tool` instead of a flat `tools/list` of hundreds — becomes the default shape for any server past a few dozen operations, because it is already how Anthropic's own code-execution-with-MCP pattern cuts a task from roughly 150,000 input tokens to 2,000, a 98.7% reduction ([layered.dev, accessed 2026-08-01](https://layered.dev/mcp-tool-schema-bloat-the-hidden-token-tax-and-how-to-fix-it/)), by having the model write code that calls tools instead of loading every schema up front. Medium confidence: static verification of tool schemas and example calls moves into the authoring loop itself — Anthropic's guidance already recommends building an evaluation harness *before* refining a tool, generating realistic multi-step tasks and improving tools based on where an agent actually fails, which is the same eval-first posture `T28-skills-design` documents for skills. Speculative: the industry converges on treating "tool count per server" the way `T28-skills-design` treats skill-listing budget — a hard, visible number you manage deliberately rather than one that silently degrades until someone benchmarks it.

---

## Mental model

```
   YOUR CODEBASE                      MCP SERVER (what you author)          AGENT

   database / files /     ──wrap──▶   TOOLS       model decides,        ◀── the model
   internal API                       one per WORKFLOW, not per         reasons about which
                                       CRUD operation                    tool to call and why

                          ──wrap──▶   RESOURCES    app decides,
                                       fixed context always attached
                                       (a README, a schema, a config)

                          ──wrap──▶   PROMPTS      user decides,
                                       named templates for repeated
                                       human-triggered requests

   THE GRANULARITY AXIS, the central design decision:

   too fine ─────────────────────────────────────────────────────▶ too coarse
   list_projects, get_project,        [ RIGHT SIZE: one tool        one god-tool:
   get_tasks, filter_tasks,           per task the caller           manage(action, payload)
   sort_tasks, format_output          actually wants done ]         12 intents, 1 schema

   burns steps assembling            composable, matches a         model must GUESS the
   primitives you already had        real request shape             internal action vocabulary
   (agent does your join for you)                                   from one opaque field
```

The one-sentence version: **a tool is a sentence the agent can act on, not a method your codebase happens to expose** — if naming it requires "and" ("get and filter and sort"), it is doing an agent's assembly work for it; if naming it requires "or" ("manage: create or update or delete or list"), it hid a decision inside a string argument instead of the tool boundary.

---

## How it actually works

### 1. Tool, resource, or prompt — the decision, applied to your own codebase

The three-way split from `T07-mcp-deep-dive` (model-controlled / app-controlled / user-controlled) becomes concrete once it is *your* code:

| Your codebase has... | Expose as | Why |
|---|---|---|
| An operation with side effects or a query whose scope varies per request (`run_migration_check`, `search_flaky_tests`) | **Tool** | The model needs to decide *when* to call it and *with what arguments*, which varies by conversation |
| A fixed reference document every session needs (your API's OpenAPI spec, a style guide, the current on-call schedule) | **Resource** | The host attaches it deterministically; no model judgment call needed to decide whether it's relevant |
| A repeated human-triggered request with a fixed shape ("summarize the last deploy", "draft a postmortem for incident X") | **Prompt** | A person explicitly invokes it; the model isn't deciding to use it mid-reasoning |

The most common authoring mistake is putting a resource's content inside a tool ("call `get_style_guide()` every time you write code" — now the model has to remember to call it) or putting a tool's job inside a resource (a static "here are the last 50 test failures" resource that goes stale the instant a new test fails, when what was needed was a `search_test_failures(query)` tool).

### 2. Tool granularity, worked before/after

Take a real shape: an internal MCP server over this repo's own curriculum system (`app/build_data.py`, `curriculum/`, `app/data/cards/`, `app/data/drillsets/` — see `T28-agent-skills-arch` for how the `/tutor-*` skills already treat this system as their source of truth).

**Too fine — the ORM-shaped first draft:**

```python
# untested sketch — anti-pattern, not a recommendation
@mcp.tool
def list_track_dirs() -> list[str]: ...
@mcp.tool
def read_file(path: str) -> str: ...
@mcp.tool
def parse_module_frontmatter(text: str) -> dict: ...
@mcp.tool
def list_card_fragment_files() -> list[str]: ...
@mcp.tool
def count_cards_in_fragment(path: str) -> int: ...
@mcp.tool
def write_file(path: str, content: str) -> None: ...
```

To answer "which modules in T28 are missing flashcards," the model must call `list_track_dirs`, then `read_file` and `parse_module_frontmatter` per module to get each `module-id`, then `list_card_fragment_files`, then `count_cards_in_fragment` per fragment, then cross-reference by hand in its own context — six-plus tool calls and a join the model is doing that your code could do in one function, for a question a human would ask in one sentence.

**Too coarse — the god-tool overcorrection:**

```python
# untested sketch — anti-pattern, not a recommendation
@mcp.tool
def curriculum(action: str, args: dict) -> dict:
    """action: one of 'list_modules', 'get_module', 'coverage_report',
    'add_module', 'write_cards', 'rebuild_index'. args shape depends on action."""
    ...
```

One schema, twelve behaviors hidden inside a string the model has to get exactly right, no per-action argument validation the model can see before calling, and every error message has to explain both what went wrong *and* which action's contract was violated. This is the MCP equivalent of a REST API with one endpoint and a `verb` field.

**Right-sized — one tool per task a caller actually wants:**

```python
# untested sketch — API shape follows FastMCP conventions,
# verified against gofastmcp.com docs, accessed 2026-08-01
from fastmcp import FastMCP
from pydantic import BaseModel

mcp = FastMCP("tutor-curriculum")

class CoverageGap(BaseModel):
    module_id: str
    title: str
    missing: list[str]   # e.g. ["cards", "drills"]

@mcp.tool
def find_coverage_gaps(track_id: str | None = None) -> list[CoverageGap]:
    """Return modules missing flashcards and/or drills, optionally scoped to
    one track (e.g. 'T28'). Use this instead of reading curriculum files and
    counting fragments by hand."""
    ...

@mcp.tool
def add_module_spec(track_id: str, slug: str, title: str, hours: float,
                     tags: list[str]) -> str:
    """Register a new module line in the track's TRACKS spec. Returns the
    generated module id. Does NOT write curriculum content — creates an
    empty slot; the module still needs to be written."""
    ...

@mcp.tool
def rebuild_index(dry_run: bool = False) -> dict:
    """Regenerate app/data from cards/drillsets/build_data.py. dry_run=True
    reports what would change (modules before/after, hours before/after)
    without writing files."""
    ...
```

`find_coverage_gaps` answers the real question in one call because the join happens in your code, where it is deterministic and free, instead of in the model's context, where it is probabilistic and costs tokens. `add_module_spec` names the actual action and its actual constraint (it creates a slot, it doesn't write content) in the docstring, because that constraint is exactly the kind of thing a model will otherwise guess wrong. `rebuild_index` has a `dry_run` because it's the one mutating tool in the set — see idempotency below.

### 3. Schema design for a reader that cannot see your code

A human integrating your API can read the source, ask you in Slack, or step through a debugger. A model has only what's in the schema and the docstring, at the moment it decides to call the tool — nothing else exists for it. Three concrete consequences:

- **Names carry meaning the model matches against, same mechanism as skill descriptions in `T28-skills-design`.** `search` versus `asana_search` versus `jira_search` is namespacing for exactly the reason two servers' generic `search` tools collide in a shared listing; Anthropic's own guidance recommends prefixing by service.
- **Enums and unions beat free-text strings wherever the value space is closed.** `status: Literal["open", "closed", "blocked"]` fails schema validation immediately on a typo; `status: str` lets a hallucinated `"in_progress"` reach your handler and either silently no-op or throw from somewhere the model can't connect back to its own mistake.
- **Docstrings should state the *contract*, not the *implementation*.** "Registers a module line; does not write content" is useful. "Appends to the `modules` list in the `TRACKS` dict in `app/build_data.py`" is an implementation detail the model doesn't need and burns tokens explaining internals nobody asked about.

### 4. Error messages written for a model, not a human

This is the single highest-leverage sentence in `T07-harness-engineering`'s tool-call contract applied to authoring: **every rejection should be an observation the model can act on, not an exception it dies on.**

```python
# untested sketch
@mcp.tool
def add_module_spec(track_id: str, slug: str, title: str, hours: float,
                     tags: list[str]) -> str:
    if not re.match(r"^T\d+$", track_id):
        # bad: raise ValueError(f"invalid track_id")
        # good: names the exact rule, shows a valid example, tells the model
        # what to do next.
        raise ValueError(
            f"track_id must match ^T\\d+$ (e.g. 'T28'), got {track_id!r}. "
            f"Call list_tracks() to see valid ids."
        )
    if slug_exists(track_id, slug):
        raise ValueError(
            f"slug {slug!r} already exists in {track_id}. Slugs must be "
            f"unique per track; module ids are the join key for cards and "
            f"drills, so renaming an existing slug after content exists "
            f"breaks those fragments. Choose a different slug, or if you "
            f"intend to edit the existing module, call get_module({track_id!r}, "
            f"{slug!r}) instead."
        )
    ...
```

A human reading `ValueError: invalid track_id` opens the source file. A model reading the same string has no source file to open — it either retries with the same bad input, or gives up and reports failure to the user. The fix costs nothing but writing the message once: name the rule, show a valid shape, name the tool that unblocks the model. Per `T07-mcp-deep-dive`, this content belongs in the `tools/call` **result** with `isError: true`, never surfaced as a raw JSON-RPC protocol error — the model needs to see it as data it can reason about.

### 5. Idempotency and dry-run, and why local servers need both more than remote ones

Retrying a tool call is the default agent behavior after a timeout or an ambiguous result (`T21-resilience-catalogue` covers the general case). For a server over your own codebase, the two guards that matter:

- **Idempotency keys on every mutating tool**, derived from `(session_id, tool_name, sorted(args))`. `rebuild_index()` called twice with identical inputs should return the same report, not run the build twice and risk a partial-write race with itself.
- **`dry_run` as a first-class parameter on anything that writes**, not an afterthought. It is the cheapest trust-building device available: an agent (or the human supervising it) can see exactly what `add_module_spec` or `rebuild_index` *would* do before it happens, which converts "the agent changed twelve files and I have to review a diff" into "the agent showed me a plan and I approved it." `git commit`, `terraform apply`, and `alembic upgrade` all offer the equivalent (`--dry-run`, `plan`, `--sql`) for the same reason, and a tool wrapping any of them should expose that flag, not hide it behind a default.

### 6. Auth and secrets in a local server

A server over your own codebase usually runs as a stdio subprocess with your own credentials already in its environment — no OAuth dance, which is both the convenience and the risk `T07-mcp-deep-dive` names as the confused-deputy problem. Three rules specific to authoring for yourself:

- **Never accept a secret as a tool argument.** If a tool signature has `api_key: str` or `token: str`, that value is now something the *model* holds and can echo back into its own context, into a later tool call, or into its final response to the user. Read secrets from the server's own environment or a local credential store at call time; the model should never see them pass through.
- **Scope the process, not the prompt.** If the server can write to disk, run it with a working-directory confinement (the sandbox boundary from `T07-harness-engineering`), not a docstring instruction not to write outside `curriculum/`. A docstring is advisory; a `chdir` + path-prefix check is enforced.
- **Log every mutating call with its actual arguments**, server-side, independent of whatever the agent's own harness traces. This is your audit trail if an agent does something wrong, and it should not depend on the agent's own logging being intact.

### 7. Testing an MCP server

Layer it, the same way `T07-harness-engineering` layers harness testing, because most of an MCP server's bugs are in ordinary code with no model involved:

| Layer | What it checks | Cost |
|---|---|---|
| Unit | Schema validation, error message content, idempotency-key derivation | Free, no model |
| Integration (`tools/list`, `tools/call`) | Correct `isError` shape, annotations (`readOnlyHint`/`destructiveHint`/`idempotentHint`) match real behavior | Free, no model |
| Trigger/selection eval | Given N realistic prompts, does the model call the *right* tool with *valid* arguments | Costs model calls; this is where granularity problems surface |
| Task-success eval | Given the tool call succeeded, did the overall task actually complete correctly | Costs model calls; this is where schema/error-message problems surface |

The `annotationHints` matter for testing, not just documentation: `destructiveHint: true` should correlate with a permission-engine `ask` decision in any harness consuming the server (`T07-harness-engineering`), so a test asserting "this tool is annotated destructive" and a test asserting "the harness gates it" should both exist and should fail independently if either drifts.

### 8. The over-tooling failure, named

**Failure mode: tool-selection collapse.** As a server's tool count grows, the observable symptom is not a crash — it's the model calling a *plausible-sounding* tool that doesn't exist, or picking the wrong one of two similarly-named tools, or (the GitHub Copilot case) an *unrelated* integration starting to misfire once a new MCP server is added to the same session, because total tool-schema token load crossed a threshold and degraded discrimination across the whole set, not just the new server's own tools. It shows up in a trace as a `tools/call` for a tool name that isn't in the `tools/list` response, or as a correctly-existing tool called with a shape from a *different* tool's schema.

Three fixes, in order of cost:

1. **Namespace by prefix** (`asana_search`, `jira_search`) — nearly free, fixes cross-server collisions immediately.
2. **Curate, don't auto-expose.** Wrapping every REST endpoint 1:1 is the reflex that creates 400-tool servers; hand-pick the twenty workflows people actually invoke and cut the rest, the way GitHub Copilot's 40→13 cut bought both latency and accuracy.
3. **Progressive disclosure / sub-servers.** Past a genuine few dozen operations, expose `list_capabilities()` and `invoke(name, args)` instead of a flat `tools/list`, or split into topic-scoped sub-servers a host can mount selectively. This is the same lever `T28-agent-skills-arch` covers for skills' listing budget, applied to tool schemas instead of skill descriptions — both are "don't pay for what you're not using this turn."

---

## Build it from scratch

Minimal server exercising every decision above — one tool per workflow, a dry-run mutating tool, model-shaped errors:

```python
# untested sketch — verified against gofastmcp.com/servers/tools, accessed 2026-08-01
from fastmcp import FastMCP
from pydantic import BaseModel, Field
import hashlib, json

mcp = FastMCP("tutor-curriculum")

_seen_keys: dict[str, dict] = {}   # naive in-memory idempotency store

class RebuildReport(BaseModel):
    modules_before: int
    modules_after: int
    hours_before: float
    hours_after: float
    would_change: bool

@mcp.tool
def find_coverage_gaps(track_id: str | None = None) -> list[dict]:
    """Return curriculum modules missing flashcards and/or drills, optionally
    scoped to one track id (e.g. 'T28'). Use this instead of reading
    curriculum files and counting fragments by hand — this does the join
    your context window would otherwise have to do."""
    gaps = []
    for mod in _load_modules(track_id):
        missing = [k for k in ("cards", "drills") if not _fragment_exists(mod, k)]
        if missing:
            gaps.append({"module_id": mod.id, "title": mod.title, "missing": missing})
    return gaps

@mcp.tool
def rebuild_index(dry_run: bool = False, idempotency_key: str | None = None) -> RebuildReport:
    """Regenerate app/data from the cards/drillsets fragments and
    build_data.py's TRACKS spec. dry_run=True reports what WOULD change
    (module/hour counts before vs after) without writing any files.
    Pass idempotency_key to make a retried call return the stored result
    instead of rebuilding twice."""
    if idempotency_key and idempotency_key in _seen_keys:
        return RebuildReport(**_seen_keys[idempotency_key])

    before = _current_counts()
    after = _compute_would_be_counts()   # pure computation, no writes
    report = RebuildReport(
        modules_before=before.modules, modules_after=after.modules,
        hours_before=before.hours, hours_after=after.hours,
        would_change=(before != after),
    )
    if not dry_run:
        _actually_rebuild()   # the only place that writes
        if idempotency_key:
            _seen_keys[idempotency_key] = report.model_dump()
    return report

if __name__ == "__main__":
    mcp.run(transport="stdio")
```

Note what's absent on purpose: no `list_modules`/`read_file`/`write_file` primitives. Anything that needs raw file access for a genuinely exploratory task should use the host's own filesystem tools (Claude Code already has `Read`/`Glob`/`Grep`) rather than reinventing them behind MCP — reserve your server's tool budget for the operations your codebase's logic actually encodes, which nothing else can do for the model.

---

## How it's done in production

| What production adds | Why it matters |
|---|---|
| **Evaluation harness before tool refinement** | Anthropic's own workflow: build a rough prototype, generate realistic multi-step tasks, run an agent against it, and let *where it fails* drive which tools get merged, split, or renamed — not intuition |
| **`annotationHints` wired to the permission engine** | `destructiveHint`/`idempotentHint`/`openWorldHint` become inputs a harness's permission engine consults for `allow`/`deny`/`ask`, per `T07-harness-engineering` |
| **Structured/typed results (`structuredContent`)** | Lets a host validate a tool's *output* shape, not just its input, catching a server-side regression before the model has to notice a malformed answer |
| **Progressive disclosure at scale** | Anthropic's code-execution-with-MCP pattern: the model writes code that calls tools instead of loading every schema up front, cutting one measured task from ~150,000 to ~2,000 input tokens |
| **Packaging as `.mcpb` (formerly DXT)** | One-click install for a local server: manifest + server + bundled deps in a zip, so a teammate doesn't hand-configure a stdio command |

### What breaks at scale

| Symptom | Cause | Fix |
|---|---|---|
| Model calls a tool name that doesn't exist in `tools/list` | Tool-selection collapse from schema-token overload across the whole session, not just this server | Namespace by prefix, curate to real workflows, or move to progressive disclosure/sub-servers |
| A newly added server makes an *unrelated* existing integration misfire | Total tool-schema token load crossed a discrimination threshold for the whole session | Same fixes as above — the new server isn't broken, the combined catalogue is |
| Agent burns most of its step budget before answering a simple question | Tools are ORM-shaped (one per CRUD op) instead of workflow-shaped | Redesign around the task a caller wants done; do the join server-side |
| Retried mutating call double-executes | No idempotency key | Derive one from `(session, tool, sorted(args))`; store-and-replay on repeat |
| Agent narrates a plausible but wrong description of what a tool will do before calling it | No `dry_run`; the model is guessing at effects instead of previewing them | Add `dry_run` to every mutating tool; make it the default in any autonomous loop |
| Secret shows up in a trace or in the model's final response | Secret passed as a tool argument instead of read server-side | Remove the parameter; read from server env/credential store at call time |
| Error crashes the client mid-await instead of being retried or explained | Tool exception surfaced as a JSON-RPC protocol error instead of `isError` content | Catch in the handler; return `isError: true` with a remediation message, per `T07-mcp-deep-dive` |

---

## Tradeoffs & when NOT to author an MCP server

- **A single in-process function nothing outside your process will ever call needs no server.** This is `T07-mcp-deep-dive`'s "wrong abstraction" case, and it applies doubly to authoring: writing a manifest, a schema, and a subprocess boundary around a function you can just call directly buys zero portability for a cost paid on every invocation.
- **Don't wrap your ORM 1:1.** If your tool list mirrors your database schema, you've shipped the too-fine failure mode by construction. The tell: naming a tool requires "get and filter and sort."
- **Don't build one god-tool "for simplicity."** A single schema hiding twelve behaviors behind an `action` string is not simpler, it's undocumented; the model has no way to discover the twelve behaviors except by trial and error against your error messages.
- **Don't expose destructive operations without a preview path.** If a mutating tool has no `dry_run` and no idempotency key, you are betting that the model never retries and never gets called twice with the same intent — a bet you will lose in any autonomous loop of nontrivial length (`T07-loop-engineering` covers exactly why retries happen).
- **Don't build the server before you've watched an agent fail at the task by hand.** The workflow-shaped tool boundary is discoverable by running the task manually with only file/shell access first, and writing down where you had to do the join yourself. Designing tools from an ER diagram instead of from an observed failure produces the ORM-shaped server every time.

---

## Interview questions

### Q1 — What determines whether something in your codebase becomes a tool, a resource, or a prompt?
**Testing:** whether you have the conceptual split or think "MCP" means "tools."
**Answer:** Who decides to use it. A tool is for the model to invoke when its judgment says so — an operation with side effects or variable scope. A resource is for the host to attach deterministically — fixed reference material every session needs. A prompt is for a human to explicitly trigger — a repeated, fixed-shape request. Misclassifying a static reference doc as a tool means the model has to remember to call it every time it's relevant; misclassifying a variable-scope query as a resource means it goes stale or can't be parameterized.
**Follow-up trap:** *"Where's the boundary blurry?"* — a search tool over a mostly-static corpus. If the corpus changes rarely and the model always wants "the current one," it can be a resource with a `resources/subscribe` for change notification instead of a tool the model has to remember to call every turn.

### Q2 — Design a server over your own codebase. Walk me through your first tool.
**Testing:** whether you reach for workflow shape or CRUD shape by default.
**Answer:** I'd first run the task by hand with only generic file/shell tools and note every place I did a join or a filter myself — that's the shape of the first tool, not an ER-diagram-derived list of getters. For example, "which modules are missing flashcards" becomes one `find_coverage_gaps()` tool that does the cross-reference server-side, instead of `list_modules` + `read_file` + `list_fragments` + manual comparison, which is six-plus calls doing work my code could do in one deterministic pass.
**Follow-up trap:** *"What if a future caller needs the raw list, not the joined answer?"* — add a second, separately named tool for that need when it's real, rather than pre-emptively exposing every primitive "just in case." An unused tool still costs listing budget and discrimination accuracy for every other tool in the session.

### Q3 — Your server has 60 tools and the model just called one that doesn't exist. Diagnose.
**Testing:** whether you know the over-tooling failure by its observable symptom.
**Answer:** Tool-selection collapse — the model hallucinated a plausible-sounding name because with a large catalogue, discrimination between real and merely-plausible tool names degrades. Benchmark data shows accuracy falling from ~19/20 at 20 tools toward complete failure past 100; a pooled unfiltered catalogue scored 13.62% in one stress test. Fix in order of cost: namespace by service prefix, cut to the workflows people actually invoke (GitHub Copilot's 40→13 cut bought both latency and accuracy), and past a few dozen genuine operations move to progressive disclosure (`list_capabilities`/`invoke`) or split into topic-scoped sub-servers.
**Follow-up trap:** *"The hallucinated tool name was plausible for a totally different, unrelated server also in the session. Why?"* — total tool-schema token load across *all* mounted servers degrades discrimination for the whole session, not per-server. Adding a new server can make an existing, previously-fine integration start misfiring; the new server isn't buggy, the combined catalogue crossed a threshold.

### Q4 — Write an error message for a tool that received an invalid `track_id`.
**Testing:** whether you write for a model or copy-paste your exception style from human-facing code.
**Answer:** Name the rule, show a valid example, and name the tool that unblocks the caller: `"track_id must match ^T\\d+$ (e.g. 'T28'), got 'track28'. Call list_tracks() to see valid ids."` A bare `ValueError("invalid track_id")` gives a human enough to go read the source; it gives a model nothing to act on except retrying the same bad input or giving up.
**Follow-up trap:** *"Where does this belong in the MCP response?"* — inside the `tools/call` result as `isError: true` content, never as a raised JSON-RPC protocol error. Protocol errors are transport faults the client SDK typically raises as exceptions mid-await, killing the run; tool failures are data the model needs to see and route around.

### Q5 — Should a tool accept an API key as a parameter?
**Testing:** the secrets-in-arguments anti-pattern, which is easy to miss because it "just works" in a demo.
**Answer:** No. Any value passed as a tool argument is now something the model holds in its own context and can echo into a later tool call, a log line, or its final response to the user. Read secrets server-side, from the process environment or a local credential store, at call time — the model should never see the value pass through at all.
**Follow-up trap:** *"What if the caller genuinely needs per-tenant credentials?"* — pass a tenant *identifier*, not the credential, and have the server resolve the identifier to a scoped credential internally. This is the same audience-validation pattern `T07-mcp-deep-dive` describes for the confused-deputy problem, applied to a local server instead of a remote OAuth flow.

### Q6 — Why does a mutating tool need both `dry_run` and an idempotency key? Aren't they redundant?
**Testing:** whether you understand they solve different problems.
**Answer:** No — `dry_run` answers "what would this do" *before* it runs, which builds trust and catches a wrong plan before any effect happens. An idempotency key answers "what happens if this exact call arrives twice," which happens routinely after a timeout or an ambiguous result in any agent loop of nontrivial length. A tool with only `dry_run` still double-executes on retry; a tool with only an idempotency key still gives the model (and any human supervising it) zero visibility into intent before the first real call.
**Follow-up trap:** *"Derive the idempotency key from what, exactly?"* — `(session_id, tool_name, sorted(args))`, hashed. Sorting the args is load-bearing: an unsorted dict serialization produces a different hash for logically identical calls whose arguments happen to arrive in a different key order, which defeats the whole mechanism silently.

### Q7 — How do you test whether your tool schemas are good, separate from whether the server works?
**Testing:** the two-question split, same shape as testing a skill's trigger accuracy versus its output quality.
**Answer:** Two separate evals. Selection: given realistic prompts, does the model call the *right* tool with *valid* arguments — this is where granularity problems surface, and it needs a should-not-trigger set too (adjacent requests that should pick a *different* tool). Task success: given the call succeeded, did the overall task actually complete correctly — this is where schema and error-message quality surface, independent of selection. A server can score well on one and poorly on the other, and conflating them hides which half to fix.
**Follow-up trap:** *"Your selection eval passes at 20 tools. Do you need to re-run it after adding ten more?"* — yes, and treat it as mandatory, not optional, the same way `T28-skills-design` treats a description edit as a behavior change requiring re-tested trigger accuracy. Tool-count degradation is nonlinear near common thresholds (the 20-tool cliff in the benchmark data), so ten more tools can cost far more accuracy than the first fifty did.

### Q8 — When would you NOT build an MCP server for an internal tool?
**Testing:** the senior "when not to" signal.
**Answer:** When exactly one agent, in one process, will ever call it — a bare function call reaches the same code in microseconds with no schema validation, no subprocess or network round trip, and no protocol surface to secure. MCP earns its cost when a genuinely different consumer (a teammate's IDE, a CI bot, a different model host) needs the same capability, or when you need real process isolation between the model host and the code. Wrapping every internal function "for consistency" with no second consumer is the same overreach `T07-mcp-deep-dive` names for the protocol generally, and it's worse for authoring specifically because you also now own a granularity design problem you didn't have before.
**Follow-up trap:** *"Your team already has three internal MCP servers with two tools each. Good architecture?"* — probably not; that's under-consolidation in the other direction. Three near-empty servers each pay their own subprocess/connection overhead and force a host to manage three mount points for six tools that could be one namespaced server. Splitting by genuine ownership boundary (a team, a system) is defensible; splitting by "it felt like a separate concern" usually isn't.

### Q9 — A tool call succeeds but the agent's final answer is wrong. Whose bug is it?
**Testing:** whether you can localize a failure between tool design and model reasoning.
**Answer:** Check the tool's returned shape first. `T27-reviewing-ai-code` documents that model confidence carries no evidentiary weight — a model narrates a wrong answer with the same fluency as a right one, so you can't diagnose from the final text. Look at what the tool actually returned: if it's a raw dump the model had to interpret (a 200-row unfiltered table when the question needed one aggregate), the tool under-delivered and the model guessed at the join; if the tool returned exactly what was asked and the model still misused it, that's a reasoning failure, which a tool redesign can't fix.
**Follow-up trap:** *"So more tool output is always safer?"* — no, it trades one failure mode for another. Anthropic's own guidance is to return only high-signal information and prioritize contextual relevance over raw flexibility; a tool that dumps everything "just in case" pushes the interpretation burden back into the model's context, which is the ORM-shaped failure again, just moved from call count into payload size.

### Q10 — Compare packaging your MCP server as `.mcpb` versus a documented stdio command.
**Testing:** whether you've thought about distribution, not just implementation.
**Answer:** A `.mcpb` (formerly DXT) bundle zips the manifest, server code, and dependencies into one file a host installs with one click — no teammate has to hand-configure a stdio command or manage a Python/Node environment themselves. A documented stdio command (a README with the exact `command`/`args` to paste into an MCP client config) costs nothing to produce but pushes setup friction onto every consumer and silently breaks the moment your dependency versions drift from theirs.
**Follow-up trap:** *"Your server needs a database connection string. Does that belong in the bundle?"* — no; the bundle ships code and declares configuration fields in its manifest, and the actual secret is supplied by whoever installs it, through the host's own credential mechanism, never baked into the bundle. Shipping a bundle with a real credential embedded is the same secrets-in-arguments mistake, just moved to build time.

### Q11 — Your codebase has both a REST API and a CLI. Which do you wrap for the MCP server?
**Testing:** whether you default to "wrap whatever exists" or actually design.
**Answer:** Neither, directly — I'd design tools around the workflows the agent needs, then implement each tool's handler by calling whichever of the REST API or CLI is more direct for that specific operation, possibly mixing both. Auto-wrapping a REST API 1:1 reproduces the too-fine failure by construction (one tool per endpoint), and auto-wrapping a CLI 1:1 has the opposite problem (each subcommand may bundle several concerns behind flags a model has to reverse-engineer from `--help` text it doesn't get to read at call time).
**Follow-up trap:** *"The REST API already has great OpenAPI docs. Why not generate tools from the spec automatically?"* — auto-generation gives you full endpoint coverage but reproduces the ORM shape at scale (dozens of endpoint-shaped tools) and inherits the API's own naming, which was designed for a human developer with the docs open, not a model with only the schema at call time. Anthropic's own guidance explicitly ships both a fully-generated coverage layer and separately hand-curated workflow tools for the same underlying API — auto-generation is a floor, not the finished design.

### Q12 — Design the permission story for a tool that can delete curriculum content.
**Testing:** whether "the model decides" ever appears in your answer for something destructive.
**Answer:** Annotate it `destructiveHint: true` in the tool spec so any consuming harness's permission engine treats it as `ask` by default, per `T07-harness-engineering`'s tool-call contract; give it `dry_run` so the effect is previewable before approval; and log the actual call server-side independent of the harness's own tracing, so there's an audit trail even if the calling agent's logs are incomplete. The model never gets to unilaterally decide this is safe — the annotation plus the harness's permission engine is the enforced boundary, and the tool's own docstring warning is advisory at best.
**Follow-up trap:** *"What if the harness consuming your server doesn't respect annotation hints?"* — then the annotation bought you nothing, which is exactly the point: annotations are hints fed into a permission decision, not a security boundary by themselves. For a genuinely irreversible operation, the deeper fix is a two-step protocol at the tool level itself — a `propose_delete` call that returns a token, and a separate `confirm_delete(token)` call — so the boundary is enforced in your code regardless of what the calling harness does with the hint.

---

## Red flags that fail you

- Wrapping every database table or REST endpoint 1:1 as a tool with no workflow design.
- A single `action`/`operation` string parameter hiding more than one behavior behind one schema.
- Error messages that read like a stack trace instead of naming the rule and the next call.
- A mutating tool with no `dry_run` and no idempotency key.
- Accepting a secret as a tool argument instead of reading it server-side.
- Claiming "more tools is more capability" with no awareness of the selection-accuracy cliff near 20-100 tools.
- No answer for "when would you not build an MCP server here."
- Testing only that the server runs, never that the model selects the right tool or that the task actually succeeds.

## Cheat card

```
TOOL vs RESOURCE vs PROMPT: who decides? model / host / human, respectively.

GRANULARITY (the central decision):
  too fine  = ORM-shaped, one tool per CRUD op -> agent does YOUR joins, burns steps
  too coarse = one god-tool with an action/verb string -> model guesses the vocabulary
  right size = one tool per task a caller actually wants DONE (workflow-shaped)

OVER-TOOLING NUMBERS (2026 benchmarks):
  ~19/20 correct @ 20 tools -> ~0/20 @ 107 tools (Speakeasy data)
  13.62% accuracy, unfiltered pooled catalogue (stress test)
  GitHub Copilot: 40->13 tools = -400ms latency, +2-5pp accuracy
  code-execution-with-MCP pattern: ~150,000 -> ~2,000 input tokens (98.7% cut)
  practical ceiling per session, industry consensus: ~5-7 MCP servers mounted

FIXES, cheapest first: namespace by prefix -> curate to real workflows
  -> progressive disclosure (list_capabilities/invoke) or topic sub-servers

SCHEMA: enums/unions over free-text where the value space is closed
  docstring = CONTRACT ("does X, does NOT do Y"), not implementation detail

ERRORS: name the rule + show valid example + name the unblocking tool
  return as tools/call RESULT isError:true, NEVER a JSON-RPC protocol error

IDEMPOTENCY: key = hash(session_id, tool_name, SORTED(args)). store-and-replay.
DRY_RUN: every mutating tool. preview effect before approval/execution.

SECRETS: never a tool ARGUMENT. read server-side (env/credential store) at call time.
  scope by process (chdir + path-prefix check), not by docstring instruction.

TESTING = TWO EVALS: selection accuracy (right tool, valid args)
  + task success (right OUTCOME). they fail independently; test both.

PACKAGING: .mcpb (formerly DXT) = manifest + code + deps, one-click install.
  stdio command doc = free but pushes setup/version-drift onto every consumer.

WRONG ABSTRACTION: one agent, one in-process function, no other consumer -> skip MCP.
```

## Sources

- [Writing effective tools for agents — with agents](https://www.anthropic.com/engineering/writing-tools-for-agents) — Anthropic Engineering; namespacing, agent-centric design philosophy, eval-before-refine workflow, prioritizing high-signal output; accessed 2026-08-01
- [How Too Many MCPs Break Your AI Agent in 2026](https://albato.com/blog/publications/embedded-mcp-context-bloat-hallucinations) — Speakeasy benchmark data (19/20 at 20 tools, failure past 107), context-bloat cross-server degradation, GitHub Copilot 40→13 result; accessed 2026-08-01
- [Adding More MCP Tools Made My AI Agent Dumber — Accuracy Collapses Past 20](https://pub.towardsai.net/adding-more-mcp-tools-made-my-ai-agent-dumber-accuracy-collapses-past-20-8e754d09bee4) — Towards AI; the 13.62% pooled-catalogue stress-test figure; accessed 2026-08-01
- [MCP Tool Schema Bloat: The Hidden Token Tax (and How to Fix It)](https://layered.dev/mcp-tool-schema-bloat-the-hidden-token-tax-and-how-to-fix-it/) — the ~150,000 → ~2,000 token reduction from code-execution-with-MCP / progressive disclosure; accessed 2026-08-01
- [Testing MCP Tool Annotations](https://sunpeak.ai/blogs/testing-mcp-tool-annotations/) — annotation-hint testing layer, dry-run and idempotency evaluation criteria; accessed 2026-08-01
- [Desktop Extensions (DXT) / MCP Bundles](https://mcp.so/dxt) and [Adopting the MCP Bundle Format (.mcpb)](https://modelcontextprotocol.info/blog/adopting-mcpb/) — packaging format, manifest structure, DXT-to-MCPB rename; accessed 2026-08-01
- [FastMCP: The Pythonic Way to Build MCP Servers and Clients](https://www.kdnuggets.com/fastmcp-the-pythonic-way-to-build-mcp-servers-and-clients) — the ~70%-of-servers estimate; accessed 2026-08-01
- `curriculum/07-agentic-ai/04-mcp-deep-dive.md` — protocol mechanics, error semantics, confused-deputy problem (this module builds on it rather than repeating it)
- `curriculum/28-ai-assisted-architecture/03-skills-design.md` — the parallel listing-budget and eval-first-testing arguments for skills, applied here to tool schemas

## Changelog
- 2026-08-01 — created
