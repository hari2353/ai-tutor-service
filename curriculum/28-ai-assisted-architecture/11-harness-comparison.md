# Harness Comparison: Claude Code vs Agent Framework vs Codex vs Cursor

> **Track:** T28 AI-Assisted Architecture (Claude) · **Time:** 2.0h · **Prereqs:** none · **Updated:** 2026-08-01
> **Module id:** `T28-harness-comparison` · **Tags:** tradeoffs, critical

## The 30-second version

Four genuinely different bets, not four flavors of the same thing: Claude Code is a terminal-first, headless-capable, model-locked-to-Anthropic coding harness that wins on permission-model granularity and CI scriptability; Codex is its closest structural twin, OpenAI-locked, structurally different at the protocol layer (a purpose-built Item/Turn/Thread wire format instead of MCP for its own control plane) and currently ahead on raw terminal-benchmark score (77.3% vs 65.4% on Terminal-Bench 2.0) while behind on diff cleanliness in blind pairwise review (Claude wins roughly two-thirds of the time); Cursor is an IDE you live inside rather than a CLI you invoke, buys multi-model flexibility (bring your own API key, no single-vendor lock-in) at the cost of a credit-metered pricing model that actively punishes large-context requests; and Microsoft Agent Framework is not a competitor to the other three at all, it's a harness-*building* SDK one level down the stack, the honest choice when none of the three finished products fit your control, observability, or compliance requirements and you're willing to own the fifteen-component harness yourself. The decision axis that actually separates these in practice is headless/CI usability crossed with lock-in: Claude Code and Codex both script cleanly into a pipeline and both tie you to one model vendor; Cursor resists scripting (it's an editor) but frees you from vendor lock-in; Agent Framework gives you both control and vendor freedom at the cost of building and maintaining the fifteen components yourself. **Every number in this module has a shelf life measured in months, not years** — this reflects the state of these tools as of 2026-08-01, and the ranking on any given axis is the kind of thing a single major release inverts.

## Why this gets asked

Because "which tool should the team standardize on" is a real decision with a real switching cost, and most candidates have used exactly one of these four and will defend it by vibes rather than by axis. The interviewer has usually watched a team make this choice for the wrong reason — picked Cursor because the IDE demo looked great and then discovered nobody could run it in CI, or picked Claude Code and then discovered the org's compliance team needed to audit every tool call in a shape none of the three finished products expose, and ended up half-building Agent Framework anyway six months later. They want to know whether you evaluate against the actual shape of your requirements (do you need headless execution, do you need multi-vendor flexibility, do you need to audit or extend the permission model) or against which tool trended on a benchmark leaderboard last week — and whether you know, unprompted, that whatever ranking you cite has already started to go stale.

---

## Lineage: past → present → future

**What came before.** Autocomplete-era tools (GitHub Copilot from 2021, early Cursor) inserted suggestions inline and left the human holding the entire control loop — when to accept, when to run a test, when to commit. The pain that killed that generation as the primary interaction model was scope: line-level suggestions don't compose into "implement this feature and verify it," because nothing owned the loop between suggestions. The 2024-2025 agentic wave (Claude Code's public launch, OpenAI's Codex CLI, Cursor's shift from Composer to autonomous agent mode) is a direct response: a harness now owns the loop — plans, calls tools, runs tests, iterates — and the human's job shifted from typing to specifying and reviewing, the general version of which `T28-claude-architect` covers in depth. Before any of the four options in this module existed as products, the only way to get agentic behavior was hand-rolling the loop yourself, which is still `T07-agent-loop-from-scratch`'s territory and still, per the tradeoffs section below, sometimes the right answer.

**Where it stands now.** The four have genuinely diverged rather than converged, and the divergence is the interesting part. Claude Code and Codex CLI are architecturally close cousins — both terminal-first, both closed-source and vendor-model-locked, both now offering local and managed-cloud execution — but they diverge sharply at the protocol layer: Claude Code's harness sits atop MCP for external tools, while OpenAI built a bespoke Item/Turn/Thread protocol over JSON-RPC/JSONL specifically because approval flows, streaming diffs, and thread persistence needed more expressiveness than a tool-oriented protocol gives (`T07-harness-engineering` covers why this matters generally). On raw benchmark performance, GPT-5.3-Codex leads Terminal-Bench 2.0 at 77.3% versus Claude's 65.4% as of this writing, which is a real, current, and specifically terminal/DevOps/scripting-weighted result — and simultaneously, blind pairwise review of the *code itself* favors Claude roughly 67% of the time on cleanliness, idiom, and diff size ([Cursor vs Claude Code vs Codex, MorphLLM, accessed 2026-08-01](https://www.morphllm.com/comparisons/cursor-vs-claude-code-vs-codex)) — two different, both-current, both-real rankings depending on what you're measuring, which is itself the module's central lesson stated as data. Cursor sits in a different category entirely: an IDE you live inside, not a terminal agent you invoke, now running parallel agents against git worktrees with best-of-n selection, priced on a credit pool that shifted from request quotas to metered usage in 2025 and split into separate first-party-model and third-party-API pools in mid-2026. Microsoft Agent Framework is the honest fourth option precisely because it refuses to compete on the same axis: Microsoft's own positioning is that the harness is "a flex point, not lock-in" — investments in LangGraph, GitHub Copilot SDK, or Claude Agent SDK carry forward into it — which only makes sense if you understand Agent Framework as an SDK for *building* a harness like the other three, not a fourth finished coding agent.

**Where it's heading.** High confidence, stated with appropriate humility given the pace: the specific numbers in this module are wrong by the time you read this, in either direction, because the four vendors are shipping monthly and the Terminal-Bench-versus-blind-review split shows the ranking already depends on which axis you pick. Medium confidence: the protocol divergence between Claude Code's MCP-based tool layer and Codex's bespoke Item/Turn/Thread protocol is a leading indicator that "the agentic coding protocol" doesn't converge to one standard the way MCP itself converged for tool access — approval flows and thread persistence appear to need more than a tool protocol expresses, and expect other harnesses to make the same bespoke-control-plane choice rather than force-fitting MCP for it. Speculative: whether Cursor's multi-model, bring-your-own-key flexibility becomes the durable differentiator against two vendor-locked terminal agents, or whether it gets matched — nothing here is stable enough to bet a design on.

---

## Mental model

Nine axes, four options, and the honest answer that none of them wins all nine:

```
                    CLAUDE CODE      CODEX (CLI)      CURSOR           AGENT FRAMEWORK
                    ────────────     ────────────     ────────────     ────────────────
LOOP CONTROL        harness-owned,   harness-owned,   harness-owned,   YOU write it;
                    27-event hooks   Item/Turn/       IDE-integrated   HarnessAgent
                    (T07-harness-    Thread protocol  agent loop w/    ships every
                    engineering)     over JSON-RPC    worktree         component
                                                       parallelism      opt-out, not in
                    ────────────     ────────────     ────────────     ────────────────
CONTEXT MGMT        5-level          own compaction   Max mode: up     you configure
                    compaction       cascade           to 1M tok       MaxContextWindow
                    cascade                            (model-         Tokens yourself;
                    (T07-loop-eng)                     dependent)      silently OFF if
                                                                        you don't
                    ────────────     ────────────     ────────────     ────────────────
TOOL ECOSYSTEM      MCP native       own protocol +    MCP support +    MCP + Semantic
                                     MCP interop       first-party      Kernel connector
                                                        + 3rd-party     ecosystem
                                                        model access
                    ────────────     ────────────     ────────────     ────────────────
PERMISSION MODEL    6 modes:         approval flows    diff accept/     you build it;
                    default/         via Item/Turn/    reject per       no default beyond
                    acceptEdits/     Thread            file/hunk        "everything on,
                    plan/auto/                                          Disable* flags"
                    dontAsk/bypass                                     (T07-harness-eng)
                    ────────────     ────────────     ────────────     ────────────────
HEADLESS / CI       `-p` flag,       yes, CLI-native   NO — it's an     yes, it's an SDK,
                    --output-format  scripting                          IDE               this is the point
                    json, GH Action
                    ────────────     ────────────     ────────────     ────────────────
COST MODEL          subscription    subscription      credit-metered, subscription
                    or API metered   or API metered    Max mode        (Foundry) or
                                                        multiplies       self-hosted infra
                                                        credit cost      cost only
                    ────────────     ────────────     ────────────     ────────────────
LOCK-IN             Anthropic       OpenAI models     LOW: BYO key,    LOW: explicitly
                    models only     only               multi-model      designed to carry
                                                                         forward other
                                                                         harness investment
```

The one-sentence version: **Claude Code and Codex are the same bet in different colors (terminal-native, model-locked, scriptable); Cursor trades scriptability for model freedom; Agent Framework refuses the trade entirely by making you own the harness, which is a fourth, structurally different answer to "which tool," not a fourth option on the same list.**

---

## How it actually works

### 1. Control over the loop

All four ultimately implement the harness pattern `T07-harness-engineering` names generally (model proposes, harness disposes), but who owns the *implementation* of that loop differs completely. Claude Code and Codex both ship the loop as a closed product — you configure it (hooks, permission modes, `AGENTS.md`/`CLAUDE.md` policy) but you don't rewrite its `while(true)`. Cursor's loop lives inside the IDE process and is even less exposed for direct modification, though its 2026 agent-window architecture (parallel agents on git worktrees, best-of-n selection) is a meaningfully different loop shape than a single-threaded terminal agent. Agent Framework inverts this entirely: `HarnessAgent`/`create_harness_agent` ships every one of the fifteen components with an explicit `Disable*` flag rather than an explicit opt-in, which is a real design signal — the framework's default posture is "you probably want all of this," and the loop itself is yours to compose, extend, or replace.

**The interview-relevant nuance:** "control over the loop" is not a single axis, it's at least two — control over *configuration* (which Claude Code and Codex both give you plenty of, via hooks and permission rules) versus control over *implementation* (which only Agent Framework and hand-rolling give you). A team that needs a custom compaction strategy, a bespoke approval workflow tied to an internal ticketing system, or a permission engine that consults a proprietary policy service needs implementation control, and none of the three finished products offer it — that's the decision point where Agent Framework or hand-rolling becomes the honest answer regardless of how good the finished products' benchmark scores are.

### 2. Context management

Claude Code's five-level compaction cascade (`T07-loop-engineering`) and Codex's own compaction are both opaque, tuned-by-the-vendor implementations you configure at the margins (thresholds, when exposed) but don't rewrite. Cursor's Max mode trades context breadth for cost directly and visibly — expanding to up to 1M tokens on models that support it, at a proportionally higher credit cost per request, which makes context management a cost-control lever a user pulls per-request rather than a harness policy. Agent Framework makes you own this explicitly, and its own documentation contains the sharpest cautionary note in this entire comparison: compaction is **silently disabled** unless you supply both `MaxContextWindowTokens` and `MaxOutputTokens` — the single most commonly reported "why did my long session die" cause in that framework, and a direct illustration of what "you own the harness" costs in practice: a missing two-parameter config, with no error, kills a long-running session in a way none of the three finished products would let happen by default.

### 3. Tool ecosystem

Claude Code is MCP-native by design. Codex interoperates with MCP but built its own control-plane protocol specifically because MCP's tool-oriented shape didn't stretch to cover approval flows and thread persistence (`T07-mcp-deep-dive` covers why MCP alone isn't sufficient for agent-to-agent or full harness control-plane needs). Cursor supports MCP servers as one tool source alongside first-party integrations and its multi-model access. Agent Framework's ecosystem draws from both MCP and Semantic Kernel's existing connector library, which is the concrete version of Microsoft's "carries forward" pitch — an org with Semantic Kernel connectors already built doesn't start from zero.

### 4. Permission model, the axis with the most real variance

This is where Claude Code's granularity is a genuine, citable differentiator rather than marketing: six distinct permission modes (`default`, `acceptEdits`, `plan`, `auto`, `dontAsk`, `bypassPermissions`), each changing what requires a human gate, plus `PreToolUse`/`PermissionRequest` hooks for custom logic, plus the `T07-harness-engineering` finding that this permission layer is explicitly *not* the same as a prose deny-list (`"the deny-list is a UX pre-filter, not a security boundary"`, the line Microsoft's own docs use for Agent Framework's shell tool and which applies equally to any of these). Cursor's permission model is coarser and more visual — accept or reject a diff, per file or hunk — which fits an IDE's interaction model but offers less programmatic control for, say, "never touch `.env` regardless of what's proposed" as an enforced rule rather than a per-diff human decision. Codex's approval flows run through its own Item/Turn/Thread protocol, giving it comparable granularity to Claude Code's but expressed through a different wire format, which matters if you're trying to build tooling that inspects or replays approval decisions across both. Agent Framework, again, gives you no default beyond "everything is on unless you disable it" — the permission model you get is the one you build.

### 5. Headless / CI usability — the sharpest practical divide

Claude Code's `-p` flag runs the full agent loop non-interactively, exits with a structured result, supports `--output-format json` for parseable output, and ships a first-party GitHub Action (`anthropics/claude-code-action`) that handles auth and rate limiting. A load-bearing caveat: `PermissionRequest` hooks do not fire in `-p` mode — enforcement in headless mode has to shift to `PreToolUse` hooks or `--allowedTools`, which is a real gotcha for anyone assuming their interactive permission setup transfers unchanged to CI. Codex CLI is comparably scriptable, CLI-native by design. **Cursor is not scriptable in the same sense at all — it is an IDE**, and the honest framing is not "worse at headless," it's "not built for headless," because the entire interaction model assumes a human watching diffs in an editor. Agent Framework, being an SDK, is headless by construction — that's what "SDK" means here — but you're writing the CI integration yourself rather than configuring a flag.

**The failure mode this produces, named:** a team picks Cursor for its IDE experience, ships a PR-review or nightly-maintenance automation requirement six months later, and discovers the tool they standardized on structurally cannot do that job — not a configuration gap, an architectural one. The fix isn't a Cursor setting; it's a second tool for the automation surface, which is a real, avoidable cost if headless usage was foreseeable at the original decision point.

### 6. Extensibility and observability

Claude Code's 27-event hook pipeline (`T07-harness-engineering`) is the most granular extensibility surface among the three finished products, letting you intercept nearly every stage of the loop. Codex's lifecycle hooks (`SessionStart`, `PreToolUse`, `PostToolUse`) cover the same categories with fewer named events. Cursor's extensibility is closer to a traditional IDE's — extensions and settings — rather than a hook pipeline into an agent loop. Observability differs by the same logic as headless usability: Claude Code and Codex both expose structured, traceable output suitable for feeding an observability pipeline (OpenTelemetry GenAI semantic conventions, per `T07-harness-engineering`); Cursor's observability is primarily the IDE's own diff/history view, built for a human watching in real time, not for a trace exported to a dashboard. Agent Framework ships OpenTelemetry on by default as part of its "everything on" posture, which is arguably its strongest single selling point for a team that already has observability infrastructure it wants agent traces to flow into.

### 7. Cost model

Claude Code and Codex both offer subscription-bundled access (bundled with Claude and ChatGPT subscriptions respectively) or metered API-key access that bypasses subscription limits — the same two-tier shape on both sides. Cursor's credit-metered model is structurally different and worth understanding precisely because it creates a direct, visible cost lever: Max mode's expanded context costs proportionally more credits per request, and the mid-2026 split into separate Composer/Auto and Third-Party-API usage pools means the actual cost depends on which models you route through, not just how much you use the tool. Agent Framework's cost is whatever infrastructure and model API costs you incur running it — there's no vendor markup on the harness itself, which is either the whole point (if you're optimizing cost at scale) or a cost you didn't previously have to engineer around (if you were relying on a finished product's pricing to be someone else's problem).

### 8. Lock-in, the axis worth being most honest about

Claude Code locks you to Anthropic's models. Codex locks you to OpenAI's. Both are, structurally, the same bet with a different vendor's name on it, and switching later means re-learning a different hook system, permission model, and CI integration, not just swapping a model string. Cursor's bring-your-own-API-key support is real lock-in relief on the *model* axis (Claude, GPT, Gemini, and others are all reachable through it) but real lock-in on the *IDE/workflow* axis — a team's muscle memory, extensions, and keybindings are Cursor-specific in a way a terminal command is not. Agent Framework's explicit pitch is that it is the low-lock-in choice on both axes simultaneously: model-agnostic by design and positioned to carry forward investment made in other frameworks (LangGraph, Semantic Kernel, Copilot SDK) — the tradeoff, stated plainly, is that this freedom is purchased with the engineering cost of owning the harness yourself.

---

## Build it from scratch

Not applicable in the usual sense — this module is a comparison, not a from-scratch build — but the honest exercise that makes the comparison concrete is scoring your *own* team's requirements against the nine axes before picking a tool, which is worth writing down as a template:

```python
# untested sketch — a scoring rubric, not a benchmark; fill in with your
# own team's actual requirements, not the numbers in this module
AXES = [
    "loop_implementation_control",  # do you need to rewrite compaction/permission logic?
    "context_management_visibility",
    "tool_ecosystem_fit",           # do your internal tools already speak MCP?
    "permission_granularity",       # per-file diff, or per-(principal,tool,arg-pattern)?
    "headless_ci_requirement",      # hard requirement, or never needed?
    "extensibility_hook_depth",
    "observability_integration",    # must traces flow into existing infra?
    "cost_predictability",          # subscription vs metered vs self-hosted-only
    "lock_in_tolerance",            # model vendor, IDE workflow, both, neither
]

def score_fit(requirements: dict[str, int], tool_profile: dict[str, int]) -> int:
    """requirements[axis] and tool_profile[axis] both 1-5. A requirement of 5
    ('must have this') on an axis where a tool scores 1 should dominate the
    result, not average it away -- a hard requirement failed is disqualifying,
    not a minor deduction."""
    for axis in AXES:
        if requirements.get(axis, 0) >= 5 and tool_profile.get(axis, 0) <= 2:
            return -1  # disqualified: hard requirement, tool can't meet it
    return sum(requirements.get(a, 0) * tool_profile.get(a, 0) for a in AXES)
```

The point of writing it as code rather than a spreadsheet: it forces the disqualification logic to be explicit. A tool that scores brilliantly on eight axes and structurally cannot do headless CI, when headless CI is a hard requirement, is not "8/9 good" — it's disqualified, and averaging the axes together is exactly how the Cursor-for-automation failure mode above gets past a review that should have caught it.

---

## How it's done in production

| What production teams actually do | Why |
|---|---|
| **Stack Cursor + Claude Code together**, not one or the other | The most commonly reported real-world combination: Cursor for in-editor, human-supervised work; Claude Code for terminal-heavy, headless, or long-running tasks — treating them as complementary rather than competing tools solves the headless-gap problem directly |
| **Pin the CI permission mode separately from the interactive one** | `PermissionRequest` hooks not firing in `-p` mode is a real, undocumented-until-you-hit-it gap; production configs explicitly re-derive CI enforcement via `PreToolUse`/`--allowedTools` rather than assuming interactive settings carry over |
| **Treat Agent Framework as the fallback when compliance needs exceed any finished product** | Audit requirements, custom approval workflows tied to internal systems, or a permission engine that must consult a proprietary policy service are the concrete triggers; teams rarely start here, they arrive here after hitting a wall in one of the three finished products |
| **Benchmark on your own workload, not the leaderboard** | The Terminal-Bench-vs-blind-review split (Codex ahead on one, Claude ahead on the other) is the standing proof that a single public ranking doesn't transfer to your specific task mix |
| **Budget Cursor's Max mode deliberately, not by default** | Credit consumption scales with context size and model choice; teams that leave Max mode on by default report materially higher spend for marginal quality gain on tasks that didn't need the wider window |

### What breaks at scale

| Symptom | Cause | Fix |
|---|---|---|
| CI job silently ignores a permission rule that worked in interactive sessions | `PermissionRequest` hooks don't fire in `-p`/headless mode | Re-derive enforcement via `PreToolUse` hooks or `--allowedTools`; test the CI permission path separately from the interactive one |
| A long Agent Framework session dies at the context limit despite "compaction enabled" | Compaction silently inactive because `MaxContextWindowTokens`/`MaxOutputTokens` weren't both supplied | Assert compaction is armed at startup; alarm if it never fires in a long session, per `T07-harness-engineering`'s identical Agent Framework gotcha |
| Cursor credit spend triples month over month with no corresponding productivity gain | Max mode left on by default; large files habitually pasted into context | Default to Auto/standard mode; reserve Max mode for tasks that specifically need the wider window |
| Team standardized on Cursor, then needed nightly automated maintenance PRs and discovered the tool structurally can't do it | Headless capability treated as a "nice to have" rather than scored as a hard requirement before adoption | Score headless/CI as a disqualifying axis up front if there's any foreseeable automation need, not an afterthought |
| Approval-flow tooling built against Claude Code's hook events breaks when the team also adopts Codex | Different control-plane protocols (MCP-based hooks vs. Item/Turn/Thread) — the "near-twin" framing hides a real integration cost | Build any cross-tool tooling (audit logging, approval dashboards) against a normalized internal event shape, not directly against either vendor's native protocol |
| A benchmark-driven tool switch produces worse real-world code quality despite a higher leaderboard score | The benchmark measured a different thing than what the team actually does (e.g., Terminal-Bench's terminal/DevOps weighting vs. a team doing mostly application-code review) | Benchmark on your own representative task sample before switching, and weight the axes your team's work actually stresses |

---

## Tradeoffs & when NOT to use each

- **Claude Code — wrong choice when:** the team lives primarily in an IDE and values in-editor diff review over terminal workflows; when multi-model flexibility (routing some tasks to a non-Anthropic model) is a hard requirement; when the org has zero appetite for vendor lock-in on the model layer.
- **Codex — wrong choice when:** the team's existing tooling and hooks are already built against Claude Code's event model and protocol, since Codex's Item/Turn/Thread shape is a different integration surface, not a drop-in swap; when the specific task mix is dominated by application-code cleanliness over terminal/DevOps throughput, where Claude's blind-review edge is the more relevant number than Codex's Terminal-Bench lead.
- **Cursor — wrong choice when:** headless or CI-triggered automation is a foreseeable requirement, since this isn't a configuration gap, it's architectural; when cost predictability matters more than model flexibility, since credit-metered pricing with a Max-mode multiplier is harder to budget than a flat subscription.
- **Agent Framework — wrong choice when:** the team needs a working coding agent *now* and has no appetite to own harness implementation, testing, and maintenance; when nobody on the team has read `T07-harness-engineering`'s fifteen-component model and internalized what "you own the harness" actually costs — Agent Framework will happily let a team ship a harness with compaction silently disabled and no idea why sessions die.
- **The one thing all four share as a "when not to":** none of them replace the judgment `T28-claude-architect` and `T27-reviewing-ai-code` cover — picking the right harness changes how fast and how cleanly code gets generated, not whether the resulting architecture and review discipline are sound. A team with weak review discipline produces bad outcomes on all four tools, just at different speeds.

---

## Interview questions

### Q1 — Compare Claude Code and Codex CLI. Are they really different products?
**Testing:** whether you can see past "both are terminal AI coding agents" to the real structural differences.
**Answer:** Structurally close cousins with one real divergence: both are terminal-first, closed, vendor-model-locked, and offer local plus managed-cloud execution, but Claude Code's control plane sits on MCP while Codex built a bespoke Item/Turn/Thread protocol over JSON-RPC specifically because approval flows and thread persistence needed more than a tool-oriented protocol expresses. On performance they diverge by axis, not uniformly: Codex leads Terminal-Bench 2.0 (77.3% vs 65.4%), a terminal/DevOps-weighted benchmark, while Claude wins roughly 67% of blind pairwise reviews on code cleanliness and diff size — different, both current, both real.
**Follow-up trap:** *"So which one's actually better?"* — the question is malformed without naming what you're optimizing for. Terminal-heavy DevOps automation favors Codex's benchmark lead; application-code quality and reviewer time favor Claude's cleanliness edge. Anyone who answers this with a single tool name and no axis is answering a different, easier question than the one asked.

### Q2 — Where is Cursor structurally unable to do something Claude Code and Codex can?
**Testing:** whether you know the headless/CI gap as architectural, not a missing feature.
**Answer:** Headless, CI-triggered execution. Cursor is an IDE — its entire interaction model assumes a human watching diffs in an editor — while Claude Code's `-p` flag and Codex's CLI-native design both run the full agent loop non-interactively with structured, parseable output. This isn't a settings gap Cursor will close with an update; it's a different category of product.
**Follow-up trap:** *"What's the practical consequence of missing this in an evaluation?"* — a team standardizes on Cursor for its IDE experience, later needs nightly automated maintenance PRs or CI-triggered fixes, and discovers the tool can't do it at all — not degraded, absent. The fix at that point is adopting a second tool, which is avoidable cost if headless need was foreseeable and scored as a disqualifying requirement up front rather than an afterthought.

### Q3 — What does Microsoft Agent Framework actually compete with, and what doesn't it compete with?
**Testing:** whether you understand it's a different kind of product, not a fourth finished coding agent.
**Answer:** It competes with hand-rolling your own harness, not with Claude Code, Codex, or Cursor directly — it's an SDK that ships all fifteen harness components (`T07-harness-engineering`) with an opt-out rather than opt-in default, and Microsoft's own positioning is explicit that it's meant to carry forward existing investment in LangGraph, Semantic Kernel, or Copilot SDK connectors rather than replace a finished coding agent.
**Follow-up trap:** *"When would a team actually reach for it over Claude Code?"* — when they need implementation control over the loop itself (a custom compaction strategy, an approval workflow tied to an internal ticketing system, a permission engine consulting a proprietary policy service) that none of the three finished products expose, and when they're willing to pay the engineering cost of owning and testing that harness themselves.

### Q4 — Your team's long Agent Framework sessions keep dying at the context limit even though you enabled compaction. Diagnose.
**Testing:** whether you know this specific, documented gotcha.
**Answer:** Compaction in Agent Framework's `HarnessAgent` is silently disabled unless you supply *both* `MaxContextWindowTokens` and `MaxOutputTokens` — a two-parameter config with no error on omission, and the single most commonly reported "why did my long session die" cause in that framework. It's a direct illustration of what "you own the harness" costs relative to a finished product like Claude Code, where compaction is on by default and tuned by the vendor.
**Follow-up trap:** *"How would you catch this before it ships?"* — assert at startup that compaction is armed, and alarm if it never fires during a session exceeding some turn count, the same invariant `T07-loop-engineering` recommends for any hand-built loop. Silent misconfiguration is exactly the class of bug you can only catch by testing the negative case, not by testing that the happy path works.

### Q5 — Design the CI integration for whichever of these four tools your team uses. What's the permission gotcha everyone misses?
**Testing:** the headless-permission-mode gap specifically.
**Answer:** For Claude Code specifically: `PermissionRequest` hooks — the interactive approval flow — do not fire in `-p` (headless) mode at all. Enforcement has to be re-derived through `PreToolUse` hooks or `--allowedTools`, which means an interactive permission setup that looks complete does not transfer unchanged to CI, and testing only the interactive path leaves the CI path unverified.
**Follow-up trap:** *"Does the same gap exist for Codex or Cursor?"* — Codex's approval flows route through its own Item/Turn/Thread protocol, so the same category of gap (interactive-only mechanisms not firing headlessly) is worth checking for explicitly rather than assuming symmetry with Claude Code; Cursor doesn't have a comparable headless mode to test in the first place, which is the deeper version of the same gap.

### Q6 — A leaderboard shows Tool A beating Tool B by 12 points on a popular benchmark. Your team is deciding which to adopt. How much does that number matter?
**Testing:** benchmark skepticism, the connecting thread of this whole module.
**Answer:** Only as much as the benchmark's task mix resembles your team's actual work. This module's own headline example is the proof: Codex leads Claude on Terminal-Bench 2.0 by 12 points, and Claude leads Codex by roughly 34 points (67% vs 33%) on blind pairwise code-cleanliness review — two real, current, both-defensible rankings of the same two tools, diverging because they measure different things. A team doing terminal/DevOps automation should weight the first; a team optimizing for reviewer time and diff cleanliness should weight the second.
**Follow-up trap:** *"So benchmarks are useless for this decision?"* — no, they're a starting hypothesis to verify against your own representative task sample, not a verdict. The mistake isn't consulting a benchmark, it's treating a single number as if it generalizes to a task mix nobody checked it against.

### Q7 — Compare the lock-in profile of Cursor versus Claude Code. Is Cursor really "lower lock-in"?
**Testing:** whether you separate model lock-in from workflow lock-in as distinct axes.
**Answer:** Only on one axis. Cursor's bring-your-own-API-key support genuinely reduces *model* lock-in — Claude, GPT, Gemini, and others are all reachable through the same IDE. But it introduces real *workflow/IDE* lock-in: a team's muscle memory, extensions, and keybindings become Cursor-specific in a way a terminal command invocation is not. Claude Code and Codex are both fully locked on the model axis and comparatively low-lock-in on the workflow axis, since a terminal agent's usage pattern (prompt in, diff out) transfers more readily to a different tool than an IDE's full interaction model does.
**Follow-up trap:** *"Which axis matters more?"* — depends on what's actually expensive to change in your org. Model lock-in mostly costs money and occasional capability ceiling; workflow lock-in costs retraining and productivity dip during a switch, which for a large team can be the larger real cost even though it's less visible in a pricing comparison.

### Q8 — When would hand-rolling your own loop (no framework, no finished product) beat all four of these options?
**Testing:** whether "build your own" is a genuine option in your mental model or a strawman you dismiss.
**Answer:** When the task is narrow enough that a fifteen-component harness is negative value — a three-to-ten-step loop with one model and a fixed, small tool set is forty lines (`T07-agent-loop-from-scratch`), and every one of these four options, including Agent Framework, carries overhead (cognitive, operational, or literal token cost) that a bare loop doesn't. It also beats all four when the requirement is genuinely unusual enough that even Agent Framework's flexibility doesn't fit — a bespoke execution environment, a non-standard model API, or a control flow that doesn't match any of these harnesses' assumptions.
**Follow-up trap:** *"Isn't that just Agent Framework with extra steps?"* — no, and the distinction is real: Agent Framework still gives you fifteen pre-built components to configure and compose; hand-rolling means none of that exists and you're accepting the maintenance burden of every future edge case (413s, cache invalidation, malformed tool calls) that `T07-harness-engineering` documents Claude Code's 1,421-line loop exists specifically to handle. Choosing hand-rolled is choosing to not have those handled until you hit them.

### Q9 — Your org needs to audit every tool call an agent makes against a compliance policy service. Which of the four fits, and why do the other three fail?
**Testing:** whether you can map a specific hard requirement to the right axis.
**Answer:** Agent Framework, because a compliance-policy-service integration requires implementation control over the permission engine — a component that consults an external service per call — which none of the three finished products expose as an extension point. Claude Code's permission modes and hooks are configurable but not replaceable at that depth; Codex's approval flow runs through its own protocol with a similarly fixed shape; Cursor's permission model is a per-diff accept/reject UI with no programmatic policy-service hook at all.
**Follow-up trap:** *"Couldn't you fake this with Claude Code's `PreToolUse` hook calling out to the policy service?"* — plausibly, for the subset of decisions a hook can gate before execution, and that's a legitimate cheaper-first attempt worth trying before reaching for Agent Framework. The honest limit: a hook is a yes/no gate on an event, not a first-class component with its own state, retries, and audit trail the way a purpose-built permission engine would be, so it degrades gracefully for simple policies and gets awkward fast for anything stateful or multi-step.

### Q10 — This module cites specific benchmark numbers (77.3%, 65.4%, 67%). How much should an interviewer trust you repeating them a year from now?
**Testing:** whether you flag the shelf-life problem unprompted, which is the module's own explicit warning.
**Answer:** Not at all without a fresh check. These are current as of 2026-08-01 and this track is explicitly the fastest-aging one in the curriculum — four vendors shipping monthly means any specific score is a snapshot, not a fact. The durable part of the answer isn't the numbers, it's the axes: loop control, context management, permission granularity, headless usability, cost model, and lock-in are stable evaluation dimensions regardless of which tool currently wins on which one.
**Follow-up trap:** *"So why memorize numbers you know will be stale?"* — because citing a specific, dated number and immediately flagging its shelf life is a stronger signal than either reciting stale numbers as current fact or refusing to engage with numbers at all. "Codex led Terminal-Bench 77.3 to 65.4 as of August 2026, and I'd re-check before making a 2027 decision on it" demonstrates exactly the evaluation discipline this whole module is testing for.

### Q11 — Design a decision process for choosing between these four for a new team, without defaulting to "whichever I already use."
**Testing:** whether you can operationalize the axes rather than just list them.
**Answer:** Score the team's actual requirements against the nine axes (loop control, context management, tool ecosystem, permission granularity, headless/CI need, extensibility, observability, cost predictability, lock-in tolerance) with hard requirements treated as disqualifying, not averaged — a tool that's excellent on eight axes and structurally can't do headless CI, when headless CI is required, is disqualified, not "mostly good." Then benchmark the surviving candidates on a representative sample of the team's actual work, not a public leaderboard, because this module's own headline example (Terminal-Bench vs. blind-review) proves a single ranking doesn't transfer.
**Follow-up trap:** *"What if two tools survive and score identically?"* — that's the point where team familiarity, existing tooling investment, and vendor relationship legitimately break the tie, and it's the *only* point in the process where "whichever I already use" is a valid input rather than the whole decision.

---

## Red flags that fail you

- Treating any one of these four as strictly "the best," with no axis named.
- Not knowing Cursor structurally cannot run headless, treating it as a settings gap.
- Confusing Agent Framework with a fourth finished coding agent rather than a harness-building SDK.
- Citing a benchmark number with no shelf-life caveat, or as if it settles the comparison.
- Not knowing that Claude Code's interactive permission hooks don't fire in headless mode.
- Conflating model lock-in and workflow/IDE lock-in as the same axis.
- No answer for when hand-rolling beats all four.
- Averaging a hard, disqualifying requirement against soft ones instead of treating it as a gate.

## Cheat card

```
FOUR DIFFERENT BETS, not four flavors of one thing:
  CLAUDE CODE  terminal, headless (-p), Anthropic-locked, MCP-native,
               6 permission modes, 27-event hooks, 5-level compaction
  CODEX (CLI)  terminal, headless, OpenAI-locked, OWN protocol
               (Item/Turn/Thread over JSON-RPC, not MCP, for control plane)
  CURSOR       IDE (NOT headless-capable -- architectural, not a gap),
               multi-model (BYO key) = low MODEL lock-in, high IDE/workflow lock-in,
               credit-metered pricing, Max mode = wider context, more credits
  AGENT FWORK  NOT a 4th finished product -- an SDK to BUILD a harness.
               ships all 15 components opt-OUT not opt-in. low lock-in on
               BOTH axes, cost = you own implementation + maintenance

NUMBERS (as of 2026-08-01, SHORT SHELF LIFE, re-check before quoting):
  Terminal-Bench 2.0: Codex 77.3% vs Claude 65.4% (terminal/DevOps-weighted)
  blind pairwise code cleanliness: Claude wins ~67% (cleanliness/idiom/diff size)
  -> SAME TWO TOOLS, opposite ranking, different axis. THIS is the module's point.

AXES (durable; the NUMBERS on them are not):
  loop control (config vs IMPLEMENTATION) · context mgmt · tool ecosystem
  · permission granularity · headless/CI · extensibility · observability
  · cost model · lock-in (MODEL axis != WORKFLOW/IDE axis, score separately)

KNOWN GOTCHAS:
  Claude Code: PermissionRequest hooks do NOT fire in -p/headless mode
    -> re-derive via PreToolUse / --allowedTools, test CI path separately
  Agent Framework: compaction SILENTLY off unless BOTH MaxContextWindowTokens
    AND MaxOutputTokens supplied -- #1 "why did my session die" cause
  Cursor: Max mode multiplies credit cost -- budget deliberately, not by default

DECISION RULE: score against YOUR axes, hard requirements DISQUALIFY (don't
  average). headless-need + Cursor = disqualified, not "8/9 good."
  benchmark on YOUR workload before switching -- leaderboards don't transfer.

WHEN NOT TO: Claude Code -- team lives in an IDE, needs multi-model.
  Codex -- existing tooling built against Claude's hook model.
  Cursor -- any foreseeable headless/CI need.
  Agent Framework -- need a working agent NOW, no appetite to own the harness.
  ALL FOUR -- none replace review discipline; weak review = bad outcomes on
  any of them, just at different speed (T28-claude-architect, T27-reviewing-ai-code).
```

## Sources

- [Cursor vs Claude Code vs Codex: IDE, Terminal Agent & Cloud Sandbox Compared](https://www.morphllm.com/comparisons/cursor-vs-claude-code-vs-codex) — Terminal-Bench 2.0 scores (77.3% vs 65.4%), blind pairwise cleanliness result (~67%), architecture/pricing/use-case comparison; accessed 2026-08-01
- [Cursor Pricing 2026: All 6 Plans & Hidden Costs](https://www.nocode.mba/articles/cursor-pricing) and [Cursor 2026 Full Breakdown: Agent Loop, Models & Pricing](https://chatgptaihub.com/what-s-new-in-cursor-2026-full-breakdown-for-developers/) — Cursor's agent-window/worktree architecture, Max mode context/credit tradeoff, mid-2026 Composer/Auto vs Third-Party-API pool split; accessed 2026-08-01
- [Claude Code Headless Mode: The Complete Self-Hosting Guide](https://amux.io/guides/claude-code-headless/) and [Claude Code permission modes: which one should your CI use?](https://backgroundclaude.com/blog/permission-modes) — `-p` flag, six permission modes, `PermissionRequest` hooks not firing headlessly, `anthropics/claude-code-action`; accessed 2026-08-01
- [Build and run agents at scale with Microsoft Foundry at Build 2026](https://devblogs.microsoft.com/foundry/agent-service-build2026/) — "harness as a flex point, not lock-in" positioning, carry-forward from LangGraph/Copilot SDK/Claude Agent SDK; accessed 2026-08-01
- `curriculum/07-agentic-ai/25-harness-engineering.md` — the fifteen-component harness model, Agent Framework's `HarnessAgent` capability table and the compaction-silently-off gotcha, Codex's Item/Turn/Thread protocol rationale; this module applies that general model to a specific four-way product comparison rather than repeating it
- `curriculum/07-agentic-ai/09-framework-matrix.md` — the adjacent comparison of agent-*building* frameworks (LangGraph, ADK, OpenAI Agents SDK, CrewAI) for teams building their own product's agent, distinct from this module's comparison of finished/near-finished *coding-assistant* harnesses
- `curriculum/28-ai-assisted-architecture/09-claude-architect.md` — why the harness choice doesn't substitute for review discipline

## Changelog
- 2026-08-01 — created
