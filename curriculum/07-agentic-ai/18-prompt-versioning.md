# Prompt Versioning, Registries, A/B Rollout, Auto-Revert on Regression

> **Track:** T07 Agentic AI · **Time:** 2h · **Prereqs:** `T07-structured-output` · **Updated:** 2026-09-06
> **Module id:** `T07-prompt-versioning` · **Tags:** production, critical

## The 30-second version

Prompts are the most-edited, least-reviewed code in most LLM systems, so they get the full software-delivery treatment: versioned as artifacts in a registry, gated by evals on a golden set, rolled out staged at 1%, 10%, 100% with traffic split by a sticky hash of user id, watched by online guardrail metrics, and auto-reverted to the last live version on regression. The reason is blast radius: a two-word wording tweak can move task completion by double digits and nothing in your diff tooling will tell you, because a prompt diff carries zero behavioral information until you run evals against it. The machinery is canary deployment applied to text: same traffic ramp, same guardrails, same auto-rollback, with prompt-cache invalidation as the one cost line unique to prompts. And if asked what to do when you don't have any of this: git plus a pinned golden set, because the eval set, not the registry, is the actual asset.

## Why this gets asked

Because every org that has shipped an LLM feature has the same war story, and interviewers use it as a discipline probe. The story: a prompt edit went out, a PM polished wording in a dashboard, or an engineer adjusted a line under a PR titled "minor cleanup," and quality regressed silently. No error fired. The unit tests passed, because they never covered tone, refusal behavior, or whether the model still emitted valid JSON after the few-shot examples were reordered. Support volume caught it three days later, and by then nobody could say which change did it, because the prompt had been edited seven times since Tuesday.

What's being probed: do you treat prompts as engineering artifacts or as strings? The candidate who hasn't shipped says "we keep them in git." The follow-ups then find out whether there's a gate on changes, a staged rollout, a revert that doesn't require a deploy, and whether the candidate has internalized that a prompt diff is behaviorally meaningless until evals run. At staff level the probe shifts to org design: five teams, one shared prompt, three services, who approves the change, and how a revert propagates before users notice.

---

## Lineage: past → present → future

**What came before.** This problem was solved twice before LLMs arrived, and prompt versioning is deliberately a re-import of those solutions. Feature flags date to Flickr in 2009 and were productized by LaunchDarkly in the 2010s; canary deploys came out of Google's Borg-era practice (progressive rollout, guardrail metrics, automated rollback), and A/B testing infrastructure is older still. Then LLM apps regressed all of it. In the 2022 to 2023 period a "prompt" was an f-string inside a service, a cell in a notebook, or a field in a vendor dashboard, and the specific pains that killed that era are worth naming because they still kill teams today. Unattributable regressions: quality dropped Tuesday and nobody can say why, because wording changes rode out under PR titles like "cleanup" and left no behavioral trace. No rollback: the previous behavior existed only as an old concatenation of three string fragments across two files plus a dashboard field, so "revert" meant archaeology, not git revert. Drift: the support copilot's system prompt differed across two services because team B copy-pasted it in March and never resynced. The next stage, prompts-in-git, fixed diffs and review but exposed a cadence mismatch: a two-word change waited on the same deploy train as a schema migration, which is how the dashboard-edit culture re-emerged through the back door.

**Where it stands now.** Three layers are consensus. First, prompts are versioned artifacts with model config attached: the prompt is not the string, it is template plus model plus sampling params plus few-shots, versioned as one unit. Langfuse ships this as open-source prompt management: versioned prompts with labels (draft, staging, production), a client-side SDK cache so retrieval is memory-speed and adds no latency, and trace links so production metrics can be sliced by prompt version; its explicit pitch is decoupling prompt updates from code deployment because PMs iterate on wording while engineers own deploys. LangSmith bundles prompt engineering into its tracing platform; PromptHub is the commercial standalone with versioning, review workflow, and deployment targets. Second, staged rollout reuses feature-flag machinery: percentage rollouts over hashed user buckets (LaunchDarkly-style) work for prompts unchanged, which matters because most orgs already run a flag platform and the fastest path is a new flag key, not a new system. Third, the eval gate: a prompt diff in CI triggers snapshot evals on a golden set, and the gate reads the scores before the rollout advances. The live disagreements are real. Prompts-in-git versus prompts-in-registry: developers want diffs, review, and blame; PMs want hotfix-without-deploy, and the honest hybrid that has emerged is registry-backed-by-repo (or export-to-git for diffing) with the label or flag doing delivery. And "are prompts code or config?" is a genuine fight: they are code-like in blast radius (they change behavior, silently) and config-like in change cadence (they need to move faster than deploys). The position that survives scrutiny: treat them as code for safety (review, eval gate) and config for delivery (instant promote, instant revert), and the eval gate is precisely what makes that split safe.

**Where it's heading.** High confidence: eval scores attached to the version, not the repo. The registry row carries its own eval results, the CI gate reads the artifact, and "what score must this change beat" becomes a property of the system rather than a tribal memory. CI gates on prompt diffs will become as unremarkable as unit tests on code diffs. Medium confidence: typed prompt interfaces. The prompt object grows placeholders with types, an output schema, and validation, so template plus schema plus few-shots plus model config ships as one deployable unit; LangChain-family prompt objects with typed placeholders point in this direction, and structured-output enforcement (the prereq module) is the output half of it. Speculative but directionally real: optimizers collapse the manual-edit loop. DSPy-style compilation (the program declares metrics, the optimizer searches over prompts against a metric) is published and works on real tasks; if it becomes standard, "prompt versioning" quietly becomes "program versioning" and the human reviews the metric delta, not the wording. Flag that as the direction of travel, not current practice; today the human reviews the wording, and that is exactly why the gate exists.

---

## Mental model

**A prompt change is a canary deploy of your agent's job description.** Same machinery as shipping code, one extra cost line (the prefix cache), and one thing that is strictly harder: the diff tells you nothing about behavior.

```
 prompt@vN ──► REGISTER: template + model + params + few-shots as ONE artifact
      │
      ▼
 CI GATE ──► snapshot eval on golden set ── score < baseline − ε? ──► REJECTED
      │ pass
      ▼
 STAGED ROLLOUT ── 1% ──► 10% ──► 100%     split = hash(user_id) mod 100, STICKY
      │                    │
      │                    └─ guardrails every window: task completion ·
      │                       cost/step · p95 latency · schema-validity rate
      ▼
 regression? ──yes──► AUTO-REVERT: repoint live label to last live version
      │               (config flip, < 1 min, NO deploy, NO build)
      no
      ▼
 vN = new baseline · vN-1 kept hot for instant rollback

 INHERITED FROM:  git → CI → canary → auto-rollback  (Google/Borg-era practice)
 UNIQUE TO PROMPTS: the diff is TEXT, carries ZERO behavioral info until
                    evals run, and every change invalidates the prefix cache
```

The sentence to remember: **a prompt diff is not information.** A code diff tells you what the program will do differently; a prompt diff tells you what the string says differently, and the mapping from wording to behavior is a black box you can only measure.

---

## How it actually works

### 1. Version semantics: semver for prompts

A prompt version number means something only if you define what "breaking" means for text.

| Bump | Meaning for a prompt |
|---|---|
| MAJOR (2.0) | changes the contract: output schema, tool vocabulary, refusal policy, persona boundaries, agent's task definition. Consumers must re-verify. |
| MINOR (1.1) | wording, few-shot order, added example, tightened instruction. Behavior may shift; schema does not. Eval gate required. |
| PATCH (1.0.1) | typo, formatting with no behavioral intent. Eval gate still required, because intent is not a guarantee. |

Two rules most teams learn the hard way. First, **model config is part of the artifact**: temperature, top_p, max_tokens, and the model id live in the same versioned row as the template. Changing temperature from 0.0 to 0.7 is a bigger behavioral change than most wording edits, and versioning the string while hot-editing the config leaves the registry lying. Second, **few-shots are not test fixtures, they are the prompt**: reordering examples is a MINOR bump with real behavioral consequences, because position in context changes attention. The failure mode this prevents is concrete: a trace from last week is unreproducible today, and you cannot say whether the template, the model, the temperature, or the example order changed.

### 2. The registry: one row, the whole artifact

```
id          "router-system"          stable, semantic, NOT auto-generated
version     27                       monotonic int (or semver string)
template    "You are the router…"    with typed variables (Jinja2 or fmt)
model       "claude-sonnet-4-6"      pinned, not "latest" — "latest" = unversioned
params      {"temperature": 0.2, "max_tokens": 2048}
schema_out  {"type":"object", …}     the structured-output contract
few_shots   [...]                    versioned WITH the template
eval_scores {"golden":"golden-v9", "score":0.84, "ran_at": …}   the gate reads this
status      draft → staged → live → rolled_back
labels      production|staging|draft (Langfuse-style labels POINT AT versions;
            "what's live" = where the production label points; rollback = repoint)
author, created_at, notes ("WHY it changed", never "what" — the diff knows what)
```

Three access patterns, three consumers. The **gate** reads `eval_scores` before allowing a promote. The **router** reads the label to pick a version at request time. The **debugger** answers "what prompt produced this trace" by logging the (id, version) pair on every call; Langfuse links prompt versions to traces so per-version production metrics are a filter, not a forensic project. "Latest" is a banned pointer in production: pinning to a version integer is what makes reproducibility and instant rollback possible. Note the honest limit: registry rows do not compose across services unless you also version the *shared* prompt ids and make services resolve the same id, which is where org discipline enters (Q10).

### 3. A/B rollout mechanics: sticky hashing and guardrails

Traffic split by deterministic hash, never per-request randomness:

```python
bucket = int(hashlib.sha256(f"{prompt_id}:{user_id}".encode()).hexdigest(), 16) % 100
arm = "v27" if bucket < canary_share else "v26"   # sticky per user, forever
```

Why sticky and not random per request: (a) a user who sees two different agent personalities in one conversation loses trust instantly; (b) per-request randomization destroys the prompt cache, since a user's conversation bounces between two prefixes and neither stays warm; (c) with a stable hash, the same user lands on the same arm across services, so metrics join cleanly. OpenAI's own caching guidance reinforces this pattern: group requests by stable keys (user, session, workspace) so the same prefix reaches the same cache.

The ramp: **1% for at least an hour, 10% for 24 to 48 hours, then 100%**, advancing only when guardrails are green. Guardrail metrics, in priority order:

| Metric | Alert threshold (example policy) | Why this one |
|---|---|---|
| task completion (verifiable outcome) | canary < baseline − 2·SE, or absolute floor at 0.70 | the metric the prompt exists to move |
| schema-validity rate | < 99% → immediate revert | a hard contract, not statistical (structured outputs) |
| cost per step (tokens × price) | > baseline × 1.15, excluding cache warm-up window | catches runaway verbosity and broken truncation |
| p95 step latency | > baseline × 1.25 | catches longer prompts and extra reasoning turns |
| guardrail hit rate (PII, injection) | > 2× baseline → immediate | safety trips are never statistical |

Auto-revert, mechanically: the monitor flips the `production` label back to the previous live version. That is a config change in the registry, sub-minute, no deploy, no build. Two design rules matter more than the thresholds: **minimum n per arm** (check at n ≥ 100; below that you are reading noise) and **hysteresis** (after the same version auto-reverts twice, quarantine it: status `rolled_back`, block re-promotion without a human, or you build an oscillator that flaps at 2am).

### 4. The prompt-cache interplay: the one cost unique to prompts

Prompt caching saves the KV state of an exact prefix; any byte change to the system prompt invalidates the entire cached prefix (Anthropic's invalidation hierarchy is `tools → system → messages`: a change at any level kills that level and everything after it). The 2026 numbers, both vendors: cache reads cost **0.1×** the base input rate (a ~90% discount, OpenAI states "up to 90%"; Anthropic's Sonnet-class pricing is $3/MTok input versus $0.30/MTok cached read), writes cost **1.25×** (5-minute TTL) or **2×** (1-hour TTL), with OpenAI's GPT-5.6-generation defaulting to a 30-minute TTL and a **1,024-token** minimum cacheable prefix. What that means for versioning, derived rather than asserted:

- **A stable prompt change is cheap.** The flip costs one 1.25× write on the changed prefix; reads then cost 0.1×. Write-once-read-fully-once totals 1.35× versus 2× for two uncached passes, and the write pays for itself after ~1.4 full reuses. Version all you want; this is not the cost problem.
- **The chronic killer is interpolation, not versioning.** A timestamp, today's date, or the user's name inside the system prompt makes the prefix unique per request: it never caches, so that segment is charged at 10× the cached rate forever. Both vendors' docs call this out as the canonical mistake; the fix is structural: static content in the cached prefix, variable content after the breakpoint. This is a prompt-registry concern because the registry is where you enforce template structure.
- **The A/B itself is cache-safe if routing is sticky.** Both arms maintain their own warm prefixes; users stay on one arm, so their conversations cache normally. Per-request random routing (the mistake) means both prefixes miss constantly.
- **One trap for the auto-revert policy:** right after a 100% flip, cache hit rate dips while the new prefix warms, and "cost per request" spikes by up to ~1.25× on input for the warm-up window. If your cost guardrail doesn't exclude that window, you will auto-revert a perfectly good change. Exclude the first window after any flip, or baseline cost in token-equivalents rather than dollars.

The observable symptom of getting this wrong: the caching dashboard shows hit rate fall from ~90% to near zero with no deploy, no model change, and no code diff, because someone interpolated `{{current_date}}` into the shared system prompt.

### 5. Diff review: what a prompt diff means (nothing, yet)

A prompt diff shows a string change. The reviewer's job is to refuse to reason from it. The mechanics that make review real:

- **The PR posts eval scores.** CI runs the golden set on the parent version and the child version and posts both. A human reviewing prose alone is reviewing intent, and intent is not a guarantee (PATCH changes have regressed double digits).
- **The diff renders, not just sources.** Templates show rendered output against a fixture input; a diff of Jinja2 fragments hides what moved where.
- **Notes carry the why.** "Refusals too aggressive on refunds; adding example 3" is reviewable. "Updated prompt" is not.
- **The gate, not the reviewer, is the safety net.** ε, the allowed score drop, is measured by running the eval twice on the same version and recording the jitter (typically 1 to 3 points on a 50 to 100 item golden set); the gate is `new_score ≥ old_score − ε`, computed, not felt.

---

## Build it from scratch

The whole system in ~55 lines: registry with an eval gate at write time, sticky-hash A/B routing, guardrail accumulation, and auto-revert. Marked honestly; production adds auth, storage, and pain.

```python
# untested sketch
import hashlib

class PromptRegistry:
    def __init__(self, eps=0.01):
        self.eps = eps        # allowed eval drop = the eval's OWN jitter (measured)
        self.rows = {}        # (id, version) -> row
        self.live = {}        # id -> live version
        self.share = {}       # id -> {version: percent}
        self.stats = {}       # (id, version) -> {n, ok, cost[], lat[]}

    def register(self, pid, version, template, model, params, evals):
        assert evals.get("score") is not None, "no eval, no entry"      # gate at WRITE
        self.rows[(pid, version)] = dict(template=template, model=model,
                                         params=params, evals=evals, status="draft")

    def promote(self, pid, version, share_pct):
        cur = self.live.get(pid)
        if cur is not None:                       # skip the gate only for the first version
            old, new = self.rows[(pid, cur)]["evals"]["score"], self.rows[(pid, version)]["evals"]["score"]
            assert new >= old - self.eps, f"eval gate: {new} < {old} - {self.eps}"
        self.rows[(pid, version)]["status"] = "staged"
        self.share[pid] = {version: share_pct, **({cur: 100 - share_pct} if cur else {})}
        self.stats[(pid, version)] = dict(n=0, ok=0, cost=[], lat=[])
        if share_pct == 100:
            self.live[pid] = version
            self.rows[(pid, version)]["status"] = "live"

    def route(self, pid, user_id, variables):
        arms = sorted(self.share[pid].items(), key=lambda kv: -kv[1])   # control = biggest
        bucket = int(hashlib.sha256(f"{pid}:{user_id}".encode()).hexdigest(), 16) % 100
        acc = 0
        for v, pct in arms[1:]:                   # challenger arms
            acc += pct
            if bucket < acc:
                return self._render(pid, v, variables)
        return self._render(pid, arms[0][0], variables)

    def record(self, pid, version, task_ok, cost_usd, latency_ms):
        st = self.stats[(pid, version)]
        st["n"] += 1; st["ok"] += task_ok
        st["cost"].append(cost_usd); st["lat"].append(latency_ms)
        self._check_revert(pid, version)

    def _check_revert(self, pid, version):
        canary = self.stats[(pid, version)]
        base_v = self.live.get(pid)
        base = self.stats.get((pid, base_v))
        if base_v is None or base_v == version or canary["n"] < 100 or base["n"] < 100:
            return                                 # min n: noise kills small canaries
        p_c, p_b = canary["ok"] / canary["n"], base["ok"] / base["n"]
        se = (p_c * (1 - p_c) / canary["n"] + p_b * (1 - p_b) / base["n"]) ** 0.5
        if p_c < 0.70 or p_c - p_b < -2 * se:      # absolute floor OR 2-sigma relative drop
            self.share[pid] = {base_v: 100}        # auto-revert = repoint, NO deploy
            self.rows[(pid, version)]["status"] = "rolled_back"

    def _render(self, pid, version, variables):
        row = self.rows[(pid, version)]
        return row["template"].format(**variables)  # real ones: Jinja2 + schema check
```

What is deliberately in those lines and what you'd add next: the gate at `register` (nothing enters without an eval score), sticky routing (the hash includes the prompt id so arms are independent across prompts), the 2-sigma OR absolute-floor revert rule, and min-n before any decision. Next in a real system: persist rows and stats, run `_check_revert` on a timer rather than inline, add the cost and latency guardrails to the revert condition, and put the eval gate in CI so `register` and `promote` can't be done from a REPL.

---

## How it's done in production

**Langfuse prompt management** (open source). Versioned prompts with labels; the production/staging/draft labels point at versions, so "rollback" is a label repoint and "what's live" is a label query. The SDK caches prompts client-side, so fetching at request time adds no latency, which removes the standard objection to a registry in the hot path. The pitch is explicitly the PM/engineer split: non-technical owners iterate on wording in the UI while engineers keep deploy rights, and prompt versions link to traces, so "completion rate by prompt version" is a built-in view, not a logging project. What it does not give you by itself: the eval gate and the rollout policy are still yours to wire (Langfuse has an evaluations suite, but the promote/revert decision logic is your pipeline's job).

**LangSmith.** Prompt engineering is bundled with the tracing platform: prompt objects with versioning, a playground, and the observability loop (traces → datasets → evals → prompt iteration) in one place. The reason to use it is the same as the reason to use Langfuse: the trace link between prompt version and production metrics already exists. Same honest caveat: the gate and the ramp policy are yours.

**PromptHub** (commercial standalone). Versioning, review workflow, and deployment targets aimed at teams that want prompt management without building it; a reasonable buy for orgs whose prompt editors are not the repo-owning engineers. Evaluate it like any vendor: what's the export path, and can you get your prompts and their history out as files.

**Feature-flag reuse.** The pragmatic default at most orgs: the prompt lives in the registry (or repo), and a LaunchDarkly-style flag does the traffic split, because the flag platform already has hashed bucketing, percentage rollouts, environments, and audit. The flag key maps to a prompt version; the flag's rollout controls the ramp. This gets you staged rollout in an afternoon; what you must add yourself is the eval gate on version changes and the online guardrails wired to prompt-version metrics, because flag platforms guardrail deploys, not behavior.

**Git-based.** Prompts as files, PR review, CI runs the golden set on every prompt diff and blocks the merge on regression; version = commit; "rollback" = revert commit + deploy. This is the right answer for teams where engineers own all prompt edits and the deploy train is fast, and it is the base layer even when a registry sits on top (export-to-git for diffing is a common hybrid). Its one real cost: delivery latency, the thing that drove PMs to dashboards in the first place.

### What breaks at scale

| Symptom | Cause | Fix |
|---|---|---|
| "Minor wording tweak" lands; support tickets +40% by Monday | direct-to-live edit bypassed the eval gate | drafts can't reach the production label without a CI eval pass; enforce in the registry API, not in convention |
| Regression found 9 days later, in a quarterly review | no online guardrails wired to prompt version | per-version task completion / cost / p95 with alerting; the trace must carry (id, version) |
| 10% canary trips the cost guardrail and auto-reverts; nothing was wrong | cost metric includes the post-flip cache warm-up (~1.25× on input) | exclude the first window after a flip; baseline in token-equivalents |
| Cache hit rate 90% → 3% overnight; no deploy, no model change | interpolated date/user name added inside the cached system prefix | static content in the prefix, variables after the breakpoint; cache-hit rate is a guardrail metric |
| PM hotfix at 18:00 Friday; prod degraded 30 min | dashboard edit with no review path | hotfix lane: gated, capped at 5%, auto-expiring timer, pager |
| Two services answer the same question differently | shared prompt drifted (one team resynced, one didn't) | one registry id for the shared prompt; ownership + change notifications to consumers |
| A/B says v2 "won" on token count; completion quietly dropped | measured the wrong primary metric | primary = verifiable task completion; tokens are a guardrail, never the goal |
| Rollout stuck at 10% for three weeks | no pre-registered promotion criteria | write the promote rule (n, soak, green guardrails) before the flip |
| Nobody can answer "what's live right now?" | live version is tribal knowledge | the `production` label is the single source of truth; every service resolves it at boot and on refresh |
| Registry outage takes the whole app down | services fetch prompts per request | client-side cache + last-known-good file on disk; the registry is on the critical path only at refresh |
| v2 rolled back but still receives traffic | router holds the version in process memory | route by label with TTL refresh + revert broadcast; never cache the version forever |
| Eval gate blocks a good change for two days | golden set too small → scores jitter past ε | grow the set (50–100+), measure ε by double-running, assert with margin |

---

## Tradeoffs & when NOT to use it

- **Solo tools and prototypes: git is the registry.** A CLI tool or a demo with one prompt, one consumer, one author needs diff, review, and revert, and git tags give all three. A registry service here is pure ops burden: uptime, auth, another SDK, another thing that can be down when you deploy. The 20% you lose (instant promote, non-dev editing, online A/B) is 20% of a small number.
- **The registry is not the asset; the golden set is.** Teams buy the platform, write 12 hand-picked eval cases, gate on them, and wonder why regressions still ship. With 12 items the gate is theater (it catches only catastrophic breakage). If you can only fund one thing, fund the eval set: mined from real traffic, 50 to 100+ items with verifiers, adversarial cases included, versioned like the prompts. A mediocre registry with a real golden set beats a beautiful registry with none.
- **When prompt changes are actually model-config changes.** Temperature bumps riding under "no prompt change, just tuning" are the most common unversioned edit in the wild. If the knob changes behavior, it's in the row. This cuts the other way too: if an org's prompts are genuinely frozen and behavior is steered by model config only, version the config with the same machinery; the registry doesn't care what string it stores.
- **Absolutism in either direction is the failure mode.** "All prompts are code, everything through full CI" for a three-person prototype ships process, not value. "All prompts are config, edit live" on a revenue-path agent is the war story from the top of this module. The split that works: code-like safety (gate, review) at the boundary of shared or revenue-bearing prompts; config-like cadence where blast radius is one internal user.
- **A registry is itself blast radius.** The dashboard is a deploy key. Access control on the production label matters as much as prod deploy permissions, and the hotfix lane must exist by design (rate-limited, capped, timed) or it will exist by shadow (someone edits prod directly at 6pm, once, and you learn from the outage).
- **Multi-model divergence is a cost of the registry, not a reason to skip it.** Per-model renderings of one prompt will diverge (different tool-call formats, different structural conventions). Version the behavioral spec once, attach per-model renderings, eval each against the same golden set; the discipline is the same, the surface is larger.

---

## Interview questions

### Q1 — Why do prompts need versioning? They're just strings.
**Testing:** whether you see prompts as behavior-bearing artifacts or as data.
**Answer:** Because a prompt is the agent's job description and every edit is a behavior change with no compiler, type checker, or test that catches it. Versioning buys four concrete things: attribution ("what changed Tuesday" answered in seconds), rollback that is a pointer flip rather than archaeology, reproducibility ("what prompt produced this trace" is a debugging requirement, so the trace must carry id and version), and the ability to gate changes on evals instead of review-by-prose. And model config belongs in the same version: temperature 0.0 → 0.7 is a bigger behavioral change than most wording edits.
**Follow-up trap:** *"We keep them in git, isn't that enough?"* — git gives diff, review, and blame, but not delivery: no staged rollout, no auto-revert without a deploy, no instant promote for non-code owners, and prompt iteration cadence ends up coupled to the deploy train, which is exactly the pressure that pushes PMs to dashboard edits. Git is the storage layer; the pipeline (gate, ramp, revert) is what's missing.

### Q2 — Design the prompt registry. What's in a row?
**Testing:** whether "the prompt" means one string or the whole artifact.
**Answer:** id (semantic, stable), monotonic version, template with typed variables, pinned model id (never "latest"), sampling params, output schema (the structured-output contract), few-shots versioned with the template, eval scores with the golden-set id they ran against, status (draft/staged/live/rolled_back), labels pointing at versions (production/staging), author and a why-note. Three consumers: the gate reads eval_scores, the router reads the label, the debugger joins traces on (id, version). Rollback is a label repoint: sub-minute, no deploy.
**Follow-up trap:** *"Why pin the model and params in the row? The prompt is the string."* — because behavior is the combination of template + model + params + example order, and versioning the string while hot-editing the temperature leaves the registry lying about what produced last week's traces. A trace that can't be reproduced against the exact artifact that made it is a forensic dead end.

### Q3 — How does the staged rollout work mechanically?
**Testing:** whether you can build the traffic split and the ramp, not just gesture at "A/B testing."
**Answer:** Deterministic sticky hash: `bucket = sha256(prompt_id + user_id) mod 100`, challenger arm gets buckets below the share. Sticky per user, forever, so a conversation never sees two arms and the prompt cache stays consistent per user. Ramp 1% (≥ 1 hour) → 10% (24–48 hours soak) → 100%, advancing only on green guardrails: task completion (primary), schema-validity rate (hard contract, immediate revert below 99%), cost per step (< 1.15× baseline), p95 latency (< 1.25× baseline). Revert flips the production label back; it's a config change, not a deploy.
**Follow-up trap:** *"Why not random 50/50 per request?"* — three reasons: users feel the personality flip mid-conversation; the cache thrashes because each user's conversation bounces between two prefixes and neither stays warm; and per-request assignment makes per-user metrics non-independent, which quietly invalidates your statistics. Sticky assignment isn't a nicety, it's what makes both the UX and the math work.

### Q4 — You're 4 hours into a 10% rollout. Canary: 400 requests, 81% completion. Control: 3,600 requests, 84%. Revert?
**Testing:** whether "revert immediately" is a reflex or a decision, and whether they can do the statistics.
**Answer:** Do the math before anything else. SE of the canary proportion: √(0.81 × 0.19 / 400) ≈ 2.0%. Control: √(0.84 × 0.16 / 3600) ≈ 0.6%. SE of the difference ≈ √(2.0² + 0.6²) ≈ 2.1%, so the observed 3-point drop is ~1.4σ: not distinguishable from noise at any reasonable confidence. So: do not treat it as a confirmed regression; also do not ignore it. The production answer is a two-tier policy: an absolute floor (any arm under, say, 70% completion reverts immediately regardless of n — that catches catastrophic breakage at n=20) and a relative rule that requires significance before it acts. With ~40 canary requests/hour, you need roughly 2,500 per arm to confirm a 3-point drop at 95%/80% power, which is ~2.6 days — so small-traffic canaries can only catch large regressions, and the design should acknowledge that instead of pretending the canary sees everything.
**Follow-up trap:** *"So you'd just wait?"* — no. Waiting is one option; the honest framing is cost asymmetry. If a regression is expensive to users (revenue path), revert on the absolute floor and investigate from a safe position; if the feature is low-stakes, let the canary accumulate n and decide with statistics. What fails the interview is answering "3% is a regression, revert" without asking for n, or "not significant, do nothing" without noting how much n you'd need and that the floor still applies.

### Q5 — What does changing a prompt do to your prompt cache, and what does it cost?
**Testing:** whether rollout conversation includes the cost line unique to prompts.
**Answer:** Prefix caches store KV state for an exact prefix; any change to the system prompt invalidates that entire cached segment and everything after it in the hierarchy (tools → system → messages). Pricing at both major vendors in 2026: reads 0.1× base input (a ~90% discount — Sonnet-class is $3/MTok input versus $0.30/MTok cached), writes 1.25× for the 5-minute TTL, 2× for 1 hour, with OpenAI's current generation defaulting to 30-minute TTL and a 1,024-token minimum. A stable version change is cheap: one 1.25× write, break-even after ~1.4 full reuses. The chronic killer isn't versioning, it's interpolation: a timestamp or user name inside the system prefix means it never caches, a permanent ~10× input cost on that segment. And one auto-revert trap: right after a 100% flip, hit rate dips while the new prefix warms; a cost guardrail that doesn't exclude the warm-up window will revert good changes.
**Follow-up trap:** *"So A/B testing prompts doubles cache cost?"* — no, if routing is sticky. Each arm maintains its own warm prefix and users stay on one arm, so their conversations cache normally. The pattern that doubles cost is per-request random split plus churning prefixes. The deeper point: cache behavior is a rollout design constraint, not an afterthought — sticky hashing is simultaneously the correct experiment design and the cache-preserving one.

### Q6 — Your golden set has 12 items. What's actually wrong with that?
**Testing:** whether they understand the gate is only as good as the eval.
**Answer:** 12 items catches only catastrophic breakage — schema violations, hard refusals, empty outputs. A 5-point regression on ambiguous cases, tone shifts, or minority-dialect inputs passes cleanly, and the gate becomes theater: "all 12 green" feels like safety while measuring almost nothing. Real sets are 50 to 100+ items mined from actual traffic (the Pareto of what users do), plus adversarial cases (PII attempts, injection, off-topic), each with a verifier — exact match where possible, rubric-based judge where not, spot-checked against human labels. Then measure the eval's own noise by running the same version twice; the jitter (typically 1–3 points) sets ε for the gate. New ≥ old − ε, computed, not felt.
**Follow-up trap:** *"We'll just add cases until regressions stop shipping."* — the failure mode there is drift toward a fixture set the prompt gets overfit to, where every version scores 0.97 and the eval stops discriminating. Two disciplines: keep a held-out slice that prompt authors don't see, and refresh the set from production continuously (real user utterances are the only source that tracks drift). An eval set that never surprises you isn't proving anything.

### Q7 — Design the auto-revert policy. Metrics, thresholds, mechanics.
**Testing:** whether the policy is a table or a vibe.
**Answer:** Layered, because "regression" has different severities. Immediate, non-statistical: schema-validity < 99%, safety guardrail hits > 2× baseline, completion below the absolute floor (0.70). Statistical (needs n ≥ 100 per arm): completion < baseline − 2·SE, cost/step > 1.15× (excluding post-flip cache warm-up), p95 latency > 1.25×. Mechanics: check every 30 minutes; revert = repoint the production label, sub-minute, no deploy; previous live stays warm for instant flip-back. Hysteresis: two auto-reverts of the same version quarantines it (rolled_back, no re-promotion without a human), or the system flaps at 2am.
**Follow-up trap:** *"Why the absolute floor if the statistical rule catches regressions anyway?"* — because statistical rules need n, and the whole point of an early canary is small n. At n=20 a catastrophic 30-point drop is blindingly obvious to a floor rule and statistically unconfirmable by a relative rule (SE at 84% with n=20 is ~8 points). The floor is what makes 1% rollouts meaningful; the statistical tier is what makes 10% rollouts honest. Systems with only one tier either revert on noise or ship catastrophes.

### Q8 — A PM wants to hotfix a prompt at 18:00 on Friday, no deploy. What's the process?
**Testing:** whether you can say yes safely, or only no.
**Answer:** The hotfix lane exists by design, because if it doesn't exist by design it will exist by shadow: someone will edit prod directly once, and you'll learn from the outage. The lane: (1) still gated — the 2-minute fast-eval on a reduced golden slice runs before promote, no exceptions; (2) capped — hotfixes promote to 5% traffic, not 100%; (3) timed — 30-minute to 2-hour auto-expiry back to the previous version unless a human confirms; (4) loud — it pages the prompt owner. Saturday-morning cleanup: the hotfix version goes through the full gate before it's allowed near 100%.
**Follow-up trap:** *"What if it's a genuine emergency, like the model is producing something harmful?"* — then the correct first move is usually the kill switch, not the prompt edit: route to the previous version (instant, one label flip) or degrade the feature. Hotfixing wording under adrenaline is how the second incident happens. The sequencing: stop the bleeding with a revert/kill, then hotfix deliberately. A candidate who reaches for "just edit it fast" in a safety scenario has told you what their Friday actually looks like.

### Q9 — Prompts in git or prompts in a registry? Pick one and defend it.
**Testing:** whether they can hold a live disagreement honestly.
**Answer:** Defend the hybrid, with the reasoning: developers need diff, review, blame — git-native. PMs and domain experts need hotfix-without-deploy — registry-native; Langfuse's entire pitch is that a two-minute wording change shouldn't wait hours or days on engineering. The position that survives scrutiny: registry as the runtime source of truth (labels, instant revert, trace-linked versions), with export-to-git or git-backed storage so every change is still diffable and reviewable. Git alone loses on delivery; registry alone loses on the review culture engineers will (correctly) demand. And the eval gate is what makes the fast path safe — it's the reason "config-like cadence" doesn't mean "config-like rigor."
**Follow-up trap:** *"That's a dodge — which do you start with?"* — git, for the first prompt you ever ship, because you already have it and the pipeline (PR + CI eval) is the part that matters. Add the registry when one of three things is true: non-engineers need to edit prompts, more than one service needs the same prompt, or you need rollback faster than your deploy train. Naming those triggers is the answer; the absolutist pick in either direction is the trap.

### Q10 — Org-level: 5 teams, 20 prompts, everyone edits their own. How do you drive adoption? (staff)
**Testing:** process leadership, not tooling.
**Answer:** Never by mandate-first; shadow dashboards and copy-paste are always available. Sequence: (1) make the loader the easiest path — a few-line SDK call with a client-side cache so the latency objection dies on contact; (2) seed it by importing existing prompts with their history so the registry starts full, not empty; (3) require it first only for shared prompts, where drift is the live, demonstrable failure (two services answering differently is your adoption slide); (4) show value — per-version metrics in the trace tool make the registry the best debugging tool in the building, not a compliance chore; (5) only then, enforce: direct prod prompt edits require the gate, because by now the gate is trusted. Expect the honest counter-argument (a team of two with a stable prompt gains little) and exempt them explicitly; blanket rules lose legitimacy at the first exception.
**Follow-up trap:** *"What's the failure mode of your sequencing?"* — step 1 without step 4: a fast loader that leads to a pile of unversioned, ungated copies in a nicer UI. The loader is a convenience; adoption is driven by the debugging value (trace → version → metric) and by shared-prompt ownership. If nobody queries "which version was live when this happened" in month two, the rollout is decorative and you should fix that before adding any policy.

### Q11 — Same logical prompt runs on Claude and GPT and an internal model. How do you version it? (staff)
**Testing:** multi-model portability without naivety.
**Answer:** They will diverge — different tool-call formats, different structural conventions (Anthropic's prompting guidance has long favored XML-style tags for Claude; other models lean markdown/JSON), different system/developer message mappings, different sampling defaults. The discipline: version the behavioral spec once (inputs, outputs, guardrails, the contract) and attach per-model renderings as variants of that one id — `router@v12[claude]`, `router@v12[gpt]` — each rendered from the same spec and each evaled against the same golden set. What must never happen: independent per-model prompt repos, because they drift independently and there is no shared definition of "regression" anymore.
**Follow-up trap:** *"Why not write one prompt that works everywhere?"* — because that's the lowest common denominator, mediocre on every model, and it still isn't stable: cross-model behavior converges and diverges as vendors ship changes, so the "universal prompt" is a moving target you've committed to never testing per-model. The spec-and-rendering split is more work and it's the only version where a regression report is meaningful, because it names which rendering moved. Also the honest cost: multi-model triples the eval surface, so it triples the golden-set investment — teams that skip that are running three unversioned systems with a shared file name.

### Q12 — When is prompt versioning the wrong answer?
**Testing:** senior judgment; every system has a wrong context.
**Answer:** Three honest cases. A solo tool or prototype with one author: git plus tags is the whole registry; a service is ops burden with negative ROI. A prompt that's genuinely frozen and low-stakes (one internal user, quarterly changes): the pipeline cost exceeds the blast radius. And an org where "prompt changes" are really model-config changes: version the config with the same machinery — the registry doesn't care what string it stores — but don't build prompt-specific template tooling for a system that never edits templates. The tell that inverts all three: the first real incident. The moment a wording change costs a day of debugging, every one of these cases graduates to "needs the pipeline," and the eval set is the part worth pre-building, because it's the asset that transfers when you adopt the machinery.
**Follow-up trap:***"How do you size the investment against blast radius?"* — one question: if this prompt regresses silently tomorrow, who notices, and how fast? If the answer is "users, in days," you need the pipeline. If it's "nobody, it's a demo," you don't. If it's "an engineer notices immediately," you need versioning (attribution, rollback) but not rollout machinery. The answer maps blast radius to machinery tiers instead of treating it as one binary.

---

## Red flags that fail you

- "We just edit it in the dashboard" with no version history, no gate, and no revert story.
- No eval gate on prompt diffs; cannot say what score a change must beat.
- Treating prompts as config-not-code, or the absolutist reverse ("every comma goes through full CI" for a prototype), with no nuance.
- Cannot name the last live version or how long a revert takes.
- A/B on token count while completion moved; "cheaper" as the win condition.
- Answering "revert!" to the canary question without asking for n, traffic, or running the statistics.
- A whole rollout-cost answer with zero mention of prefix-cache invalidation.
- "Our prompts never change" (they will, and the first change is the war story).
- A golden set of 12 hand-written happy cases, called "the eval suite."
- A hotfix path with no cap, no timer, and no pager.
- Versioning the template while hot-editing temperature and model id.

---

## Cheat card

```
PROMPTS = BEHAVIOR-BEARING CODE. version + review + staged rollout + auto-revert
  a "harmless wording tweak" moves task completion by double digits and the DIFF
  TELLS YOU NOTHING — behavior is only knowable through evals

PIPELINE  register(template+model+params+few_shots) → eval gate on golden set
          (new ≥ old − ε, ε = eval's OWN jitter ~1-3pts) → 1% (≥1h) → 10% (24-48h)
          → 100% → guardrails → auto-revert = repoint label, <1 min, NO deploy

SEMVER   MAJOR = contract change (schema, tools, refusal policy)
         MINOR = wording/examples (eval-gated)   PATCH = typo (STILL eval-gated)
         model + temp/top_p ARE PART OF THE ARTIFACT — version them together

REGISTRY ROW  id · version · template · model · params · schema_out · few_shots
              · eval_scores · status(draft|staged|live|rolled_back) · labels
              "what's live" = production LABEL. rollback = repoint. never "latest"

SPLIT    sha256(prompt_id + user_id) mod 100 → STICKY per user, every service
         NEVER random per request (cache thrash + users feel the flip)
GUARDRAILS   task completion (primary) · schema-validity <99% → instant revert
         · cost/step >1.15× (EXCLUDE post-flip cache warm-up!) · p95 >1.25×

STATS    SE = √(p(1−p)/n).  canary n=400 @ 81% vs control 84% → Δ3% ≈ 1.4σ
         = NOISE.  3-pt drop needs ~2,500/arm (95%/80%) → small canaries only
         catch BIG regressions: absolute floor (completion < 0.70 → revert at any n)
         + 2-sigma relative rule (n ≥ 100/arm). 2 reverts = quarantine (no flapping)

CACHE    prefix = exact match. system-prompt change invalidates everything after
         reads 0.1× · writes 1.25× (5m) / 2× (1h) · OpenAI 30m TTL, 1,024-tok min
         stable change = one-time 1.25× write, break-even ~1.4 reuses = CHEAP
         CHRONIC KILLER = interpolated date/user-id INSIDE the prefix → NEVER
         caches = ~10× input cost on that segment, forever (hit-rate 90%→~0 = symptom)

HOTFIX LANE (exists by design or it exists by shadow)
         gated fast-eval → 5% cap → 30m-2h auto-expire → pager → full gate later

WHEN NOT  solo/prototype → git+tags IS the registry; service = ops burden
          THE GOLDEN SET IS THE ASSET: 50-100+ real items + adversarial + held-out
          12-item golden set = gate theater. blast radius: "who notices, how fast?"
```

## Sources

- [Langfuse — Prompt Management (overview)](https://langfuse.com/docs/prompt-management) — decoupling prompt updates from code deployment, PM/engineer split, client-side SDK caching ("as fast as reading from memory"), version control and labels, linking prompts to traces for per-version performance analysis; accessed 2026-09-06
- [Langfuse — Prompt version control and environments](https://langfuse.com/docs/prompt-management/features/prompt-version-control) — versioning, labels (draft/staging/production), environment promotion; accessed 2026-09-06
- [Anthropic — Prompt caching](https://platform.claude.com/docs/en/build-with-claude/prompt-caching) — pricing multipliers (read 0.1×, 5m write 1.25×, 1h write 2×), Sonnet-class $3/MTok input vs $0.30/MTok cached read, tools→system→messages invalidation hierarchy, 4 explicit breakpoints, 20-block lookback, 5-minute/1-hour TTLs, write-once-read-once = 1.35× vs 2× arithmetic, the "breakpoint on changing content" mistake; accessed 2026-09-06
- [OpenAI — Prompt caching](https://platform.openai.com/docs/guides/prompt-caching) — cached input discounted up to 90%, 1,024-token minimum (GPT-5.6 and later), writes 1.25× / reads 0.1×, 30-minute default TTL, `prompt_cache_key` grouping and sharding, settings that invalidate the prefix (tools, model, reasoning effort), "keep the prefix stable" guidance; accessed 2026-09-06
- [LangSmith documentation](https://docs.smith.langchain.com/observability) — platform note: all deployment options include observability, prompt engineering, and deployment; traces to datasets to evaluation loop; accessed 2026-09-06
- [PromptHub](https://www.prompthub.io) — commercial prompt-management platform: versioning, review workflow, deployment targets (kept conservative; JS-rendered site, positioning verified from homepage metadata); accessed 2026-09-06
- [LaunchDarkly docs](https://docs.launchdarkly.com) — feature-flag percentage rollouts and hashed bucketing, the machinery reused for staged prompt rollout; accessed 2026-09-06
- [DSPy](https://dspy.ai) — prompt optimization as compilation against declared metrics, the basis for the "where it's heading" claim; accessed 2026-09-06

## Changelog
- 2026-09-06 — created
