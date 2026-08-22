# Loop Engineering: The Canonical Loop, Budgets, Compaction Triggers, Stop Conditions

> **Track:** T07 Agentic AI · **Time:** 3h · **Prereqs:** `T07-agent-loop-from-scratch`, `T07-harness-engineering`, `T07-context-engineering` · **Updated:** 2026-07-26
> **Module id:** `T07-loop-engineering` · **Tags:** sprint, harness, critical

## The 30-second version

The loop is forty lines; the *controls* are two thousand, and Claude Code's production loop body is 1,421 lines with nine distinct `continue` points because 413s, cache invalidation, prompt-too-long recursion and 500-turn sessions are all real. Loop engineering is four things done properly: **budgets** that are hierarchical and reserved rather than checked (steps, tokens, cost, wall-clock, and the distinction between context tokens which drive compaction and billed tokens which drive cost); **compaction triggers** ordered cheapest-first with correct token accounting, because freeing tokens without updating the threshold calculation makes the expensive compactor fire anyway; **the full stop-condition set** including a progress detector that measures state delta rather than argument-hash repeats; and **resumability**, which means a typed event log and deterministic context assembly, not a pickled process. The arithmetic that justifies all of it: at 0.90 per-step success a 12-step task completes 28% of the time, and each control buys a measurable slice back, with checkpoint-and-resume the single largest jump (roughly 48% to 75% in the worked model below). Everything else in this module is how to make those numbers true.

## Why this gets asked

Because module 01's answer, six stop conditions and three budgets, is now the *floor*. In 2026 an interviewer at a company that runs agents in production will accept that answer and immediately go one level down, because that is where their incidents live. The specific incidents: parallel subagents that each checked the same shared budget, all passed, and collectively spent 5× the cap (a time-of-check-to-time-of-use bug on money); a compaction that fired and destroyed the pointer to a persisted 2 MB tool output the agent needed three turns later; a run that could not be resumed after an approval because the "checkpoint" was a serialized Python object whose class had changed; and the one Anthropic published telemetry for, 1,279 sessions with 50+ consecutive compaction failures, worst case 3,272, burning roughly 250,000 API calls per day until someone added a three-line circuit breaker. Every one of those is a loop-engineering bug, not a model or prompt bug. The question behind the question is whether you have ever owned the loop when it was on fire.

---

## Lineage: past → present → future

**What came before.** The 2022 ReAct loop had no controls at all, by design: it was a prompting result, and the harness was a notebook. AutoGPT in 2023 added autonomy and nothing else, and the specific pain that killed it was not that it failed, it was that it failed *expensively and invisibly*: no cost ceiling, no deadline, no progress detection, so the canonical AutoGPT failure was an overnight run that rediscovered the same dead end forty times and produced a bill instead of a result. The 2024 framework generation (LangChain agents, early CrewAI) added a step cap and called the problem solved. That was the second pain: a step cap alone fails in exactly the ways that matter, because it does not bound cost (a 25-step run with a tool returning 50 KB per call costs dollars), does not bound latency, and does not detect that the model is stuck. LangGraph's 2024/2025 contribution was the one that actually mattered: making state explicit and checkpointable, because at realistic per-step reliability most multi-step runs fail somewhere and the difference between restart and resume is the difference between a demo and a product.

**Where it stands now.** Three things settled and one is actively contested. **Settled: progressive, tiered context management replaced single-threshold compaction.** The reverse-engineering of Claude Code published in April 2026 documents five sequential shapers, cheapest first: budget reduction, snip, microcompact, context collapse, autocompact. Four of the five cost zero API calls. Most sessions never reach the fifth, and that is the design goal, not an accident. **Settled: token accounting anchors on server-reported usage.** Pure client-side tokenizer estimation carries 30%+ error, which is enough to fire compaction too early (wasting the cache) or too late (413). Anchoring on the `usage` field from the last API response and estimating only the delta since then gets under 5%. **Settled: the loop is a state machine, not recursion.** Early Claude Code used recursion and blew the call stack on long conversations; the current design is `while(true)` with an explicit state object, and each `continue` is a named transition. **Contested: who triggers compaction.** Harness-controlled at a token threshold is the default, but LangChain's autonomous-context-compression work and the Active Context Compression paper (22.7% token reduction, no accuracy loss on long-horizon tasks) argue the agent should call a compression tool when it judges the moment safe, because reactive-at-limit compaction interrupts a subtask mid-flight and corrupts in-progress reasoning state. Also contested: whether execution should be streaming. Claude Code starts tool 1 while the model is still generating tool call 3, and reports a 5-call turn going from 30s sequential to 18s, a 40% latency win from architecture alone. The counter-argument is that it makes ordering and cancellation semantics genuinely harder, and cancellation correctness is where the bugs are.

**Where it's heading.** **High confidence: budget and deadline become model-visible context, not just harness-side gates.** The result driving this is that temporal awareness appears orthogonal to reasoning capability, and injecting explicit remaining-budget and deadline information into context significantly improves performance on deadline-constrained tasks. Harness-side enforcement alone wastes capability; the model can triage if you tell it what it has left. LangChain ships this as time-budget warnings in context. **Medium confidence: hibernate-and-wake becomes the standard shape for anything over an hour.** Meta's Ranking Engineer Agent checkpoints and resumes interrupted 6-hour tasks across multi-day ML pipelines; Anthropic's initializer-agent-hands-off-to-coding-agent pattern uses feature lists, git commits, and test gates as cross-session state. Both are the same insight: when a task exceeds one context window, the loop must be able to *end* and be *resumed by a fresh context*, which is a stronger requirement than checkpointing within a run. **Low confidence, speculative: formal scheduler models for loop choice.** An April 2026 analysis of 70 open-source agent projects found 60% use the plain Agent Loop pattern and proposes a unified scheduler framework mapping Agent Loop / event-driven / state-machine / graph-flow / hybrid onto explicit controllability-expressiveness-implementability trade-offs. Intellectually clean; I have not seen anyone pick a loop architecture with it yet.

---

## Mental model

The loop is a state machine whose transitions are named, and every named transition is a bug you have already had:

```
                      ┌──────────────────────── state ────────────────────────┐
                      │ messages[] · tree_steps · local_steps · billed_tokens  │
                      │ context_tokens · usd · deadline(abs) · phase           │
                      │ compaction_failures · reactive_compact_attempted       │
                      │ open_items[] · checkpoint_seq · transition_reason      │
                      └───────────────────────────────────────────────────────┘
                                            │
   ┌────────────────────────────────────────▼─────────────────────────────────────┐
   │  1. SHAPE CONTEXT      cheapest-first: budget-reduce → snip → micro →         │
   │                        collapse → autocompact        (4 of 5 cost zero calls) │
   │  2. PRE-CALL GATES     budgets? deadline? compaction circuit breaker?         │
   │  3. INJECT AWARENESS   remaining steps / tokens / seconds INTO context        │
   │  4. CALL MODEL         streaming; tools may start before generation ends      │
   │  5. ERROR RECOVERY     413 → reactive compact (ONCE) · 5xx → retry · fallback │
   │  6. POST-CALL GATES    budgets again; stop hooks                              │
   │  7. NO TOOL CALLS?     ──▶ VERIFY (deterministic) ──▶ DONE or continue        │
   │  8. EXECUTE TOOLS      validate → permit → sandbox → shape result             │
   │  9. PROGRESS CHECK     state delta? todo delta? repeat hash? → intervene      │
   │ 10. CHECKPOINT         append typed events; fsync; advance checkpoint_seq     │
   └────────────────────────────────────┬─────────────────────────────────────────┘
                                        │ continue (with a NAMED reason)
                                        └──▶ back to 1
```

The single idea that makes the rest fall out: **the loop has two distinct token quantities and confusing them is the most common budget bug.**

```
  context_tokens   what is in THIS agent's window right now
                   → drives COMPACTION. Shrinks when you compact. Per-agent.

  billed_tokens    everything the run has ever paid for, including every
                   subagent's isolated context and every compaction summary call
                   → drives COST. Monotonically increases. Never shrinks. Per-RUN.
```

Compaction reduces `context_tokens` and *increases* `billed_tokens` (the summarizer call costs money). If you enforce your cost budget against `context_tokens`, compaction makes your cost budget look like it is going *down* while you spend. That is a real bug and it is easy to write.

---

## How it actually works

### The canonical loop, with every control in place

```python
# untested sketch - production shape, ~180 lines with the controls, not 40
import time, json, hashlib, collections
from dataclasses import dataclass, field

# ─────────────────────────── budgets ───────────────────────────

@dataclass
class Budget:
    """Hierarchical. A subagent gets a CHILD budget carved out of this one."""
    run_id: str
    # limits
    max_local_steps: int = 25          # iterations of THIS loop
    max_tree_steps: int = 120          # iterations across this loop + all descendants
    max_billed_tokens: int = 2_000_000 # cost driver, includes subagents + summarizers
    max_usd: float = 5.00
    deadline_mono: float = field(default_factory=lambda: time.monotonic() + 900)
    context_window: int = 200_000
    max_output_tokens: int = 16_384

    # counters
    local_steps: int = 0
    tree_steps: int = 0                # shared object with children, see reserve()
    billed_tokens: int = 0
    context_tokens: int = 0            # per-agent, reset downward by compaction
    usd: float = 0.0

    # loop hygiene
    compaction_failures: int = 0
    reactive_compact_attempted: bool = False

    MAX_CONSECUTIVE_COMPACTION_FAILURES = 3   # circuit breaker

    def stop_reason(self) -> str | None:
        if self.local_steps  >= self.max_local_steps:    return "local_step_budget"
        if self.tree_steps   >= self.max_tree_steps:     return "tree_step_budget"
        if self.billed_tokens>= self.max_billed_tokens:  return "token_budget"
        if self.usd          >= self.max_usd:            return "cost_budget"
        if time.monotonic()  >= self.deadline_mono:       return "deadline"
        if self.compaction_failures >= self.MAX_CONSECUTIVE_COMPACTION_FAILURES:
            return "compaction_circuit_breaker"
        return None

    def remaining(self) -> dict:
        return {
            "steps": self.max_local_steps - self.local_steps,
            "usd": round(self.max_usd - self.usd, 4),
            "seconds": max(0, int(self.deadline_mono - time.monotonic())),
            "context_pct": round(100 * self.context_tokens / self.context_window),
        }

    def reserve(self, *, steps: int, usd: float, tokens: int) -> "Budget":
        """Carve a child budget. RESERVE eagerly so parallel children cannot
        collectively overshoot. Reconcile actuals on return."""
        if self.usd + usd > self.max_usd:
            raise BudgetExhausted("cannot reserve child cost budget")
        self.usd += usd                      # pessimistic debit NOW
        self.billed_tokens += tokens
        child = Budget(
            run_id=self.run_id,
            max_local_steps=steps,
            max_usd=usd,
            max_billed_tokens=tokens,
            deadline_mono=self.deadline_mono,   # ABSOLUTE, inherited, not a duration
            context_window=self.context_window,
        )
        child._parent = self                   # for reconcile + tree_steps
        return child

    def reconcile(self, child: "Budget", reserved_usd: float, reserved_tokens: int):
        """Return unspent reservation to the parent."""
        self.usd            -= (reserved_usd - child.usd)
        self.billed_tokens  -= (reserved_tokens - child.billed_tokens)
        self.tree_steps     += child.tree_steps or child.local_steps

# ─────────────────────────── the loop ───────────────────────────

def run(task, tools, budget, store, trace, resume_from=None):
    if resume_from:
        state = store.rehydrate(resume_from)          # deterministic replay
    else:
        state = State(messages=[system_msg(), user_msg(task)], open_items=[task])
        store.append(Event("user_message", content=task))

    seen = collections.Counter()
    last_progress_signature = None
    steps_without_progress = 0

    while True:
        it = trace.start("iteration", n=budget.local_steps, run=budget.run_id)

        # ── 1. shape context, cheapest first ──────────────────────────────
        try:
            state, freed = shape_context(state, budget)     # see next section
            budget.context_tokens -= freed
            budget.compaction_failures = 0
        except CompactionFailed as e:
            budget.compaction_failures += 1
            trace.event("compaction_failed", n=budget.compaction_failures, err=str(e))

        # ── 2. pre-call gates ─────────────────────────────────────────────
        if (reason := budget.stop_reason()):
            return finish(it, state, stop_reason=reason)

        # ── 3. make the budget model-visible ──────────────────────────────
        state = with_budget_reminder(state, budget.remaining())

        # ── 4. call the model ─────────────────────────────────────────────
        try:
            resp = call_model(state.messages, tools.schemas(budget.phase),
                              max_tokens=budget.max_output_tokens)
        except PromptTooLong:
            # ── 5. error recovery: reactive compact, ONCE per turn ────────
            if budget.reactive_compact_attempted:
                return finish(it, state, stop_reason="prompt_too_long_unrecoverable")
            budget.reactive_compact_attempted = True
            state = emergency_compact(state)
            trace.event("reactive_compact")
            continue                                    # transition: reactive_compact
        except RateLimited as e:
            trace.event("rate_limited", retry_after=e.retry_after)
            if time.monotonic() + e.retry_after >= budget.deadline_mono:
                return finish(it, state, stop_reason="deadline")
            time.sleep(e.retry_after)
            continue                                    # transition: rate_limit_retry
        except ModelUnavailable:
            if not tools.can_fallback():
                return finish(it, state, stop_reason="model_unavailable")
            trace.event("model_fallback")
            continue                                    # transition: model_fallback

        budget.local_steps += 1
        budget.tree_steps  += 1
        budget.billed_tokens += resp.usage.input_tokens + resp.usage.output_tokens
        budget.usd           += price(resp.usage)
        budget.context_tokens = anchor_token_count(resp.usage, state)  # <5% error
        budget.reactive_compact_attempted = False

        state.messages.append(assistant_msg(resp))       # PRESERVE thinking blocks
        store.append(Event("assistant_message", usage=resp.usage))

        calls = [b for b in resp.content if b.type == "tool_use"]

        # ── 6/7. natural termination requires VERIFICATION ────────────────
        if not calls:
            ok, evidence = verify(state, task)           # deterministic, not the model
            if ok:
                return finish(it, state, stop_reason="verified_complete")
            if budget.stop_reason():
                return finish(it, state, stop_reason="unverified_at_budget")
            state.messages.append(user_msg(
                f"Verification failed: {evidence}. Open items: {state.open_items}. "
                f"Continue, or explain why you cannot."))
            continue                                     # transition: verification_failed

        # ── 8. execute ────────────────────────────────────────────────────
        results = []
        for c in calls:
            results.append(handle_tool_call(c, tools, budget, trace))  # see T07-harness
            store.append(Event("tool_call", name=c.name, id=c.id))
        state.messages.append(tool_results_msg(results))  # 1:1 with tool_use ids

        # ── 9. progress detection: state delta, not just arg hashes ───────
        sig = progress_signature(state)      # (files_changed, tests_passing, todos_closed)
        if sig == last_progress_signature:
            steps_without_progress += 1
        else:
            steps_without_progress, last_progress_signature = 0, sig

        key = [(c.name, json.dumps(c.input, sort_keys=True)) for c in calls]
        for k in key:
            seen[k] += 1

        if any(seen[k] >= 3 for k in key):
            state.messages.append(user_msg(
                "You have called this exact tool with these exact arguments 3 times. "
                "It will not produce a different result. Change approach or explain "
                "why you cannot proceed."))
        elif steps_without_progress >= 4:
            state.messages.append(user_msg(
                f"No observable state change in {steps_without_progress} steps: no file "
                f"modified, no test outcome changed, no todo closed. Re-read the task, "
                f"state your current hypothesis, and pick a different approach."))

        # ── 10. checkpoint ────────────────────────────────────────────────
        store.checkpoint(state, budget)                  # append-only, fsync
        trace.end(it, transition="tool_result")
```

Note the four things that are *not* in module 01's version and are the whole point of this module: `tree_steps` alongside `local_steps`; `billed_tokens` alongside `context_tokens`; verification gating natural termination; and a progress detector keyed on state delta rather than only on argument-hash repeats.

### Budget accounting across nested subagents

This is where most people's model breaks, and it is a genuinely good interview question because it maps onto distributed-systems fundamentals the candidate already has.

**Four quantities, four different composition rules:**

| Quantity | Composition | Trap |
|---|---|---|
| **Steps** | Two counters: `local_steps` (this loop) and `tree_steps` (shared, whole run) | A child's steps must not consume the parent's local cap (the parent would terminate early) but must consume the run's total cap (otherwise N children multiply your ceiling by N) |
| **Cost (USD)** | Strictly additive up the tree, and must be **reserved**, not checked | Check-then-spend is a TOCTOU bug on money. N parallel children each read the shared remaining budget, all pass, all spend → overshoot by up to N× |
| **Billed tokens** | Additive up the tree, including summarizer calls | A subagent's tokens do *not* enter the parent's context but *do* enter the run's bill |
| **Wall-clock deadline** | Inherited as an **absolute monotonic timestamp**, never as a duration | Pass `timeout=600` and each of three nested levels gets its own 600 seconds; total 1,800. Pass `deadline_mono=T` and the whole tree shares one horizon |

**The reservation pattern, stated precisely.** At delegation time, the parent pessimistically debits the child's maximum from its own remaining budget, hands the child a budget object whose caps equal that reservation, and on return credits back `reservation - actual`. This makes parallel fan-out safe without a lock, because the debit happens once in the parent's thread before any child starts. The failure symptom if you skip it: p99 run cost sitting at roughly `fanout ×` your configured cap, with every individual subagent's trace showing it stayed under budget. That is the tell, and it is confusing the first time you see it, because nothing looks broken locally.

**The context-isolation asymmetry.** A subagent exists partly to keep its 40 KB of exploratory tool output out of the parent's window; LangChain's measured figure is that subagents process 67% fewer tokens than skills in multi-domain scenarios for exactly this reason. But that isolation is a *context* property, not a *cost* property. Concretely: three research subagents each burning 120K context tokens contribute 360K to `billed_tokens` and roughly nothing to the parent's `context_tokens` beyond their returned summaries. If your dashboard plots one number called "tokens," you will not be able to explain your bill.

**Compaction inside a subagent is billed to the run.** Every autocompact forks a summarizer call. A deep tree with aggressive compaction can spend a meaningful fraction of the run's budget on summarization, which is invisible if you only count the primary model's usage. Instrument it: emit `compaction_events` and `compaction_cost_usd` per run, and alert if compaction exceeds ~10% of run cost, because at that point the right fix is upstream (truncate tool results harder) not more compaction.

**Cancellation.** When the parent's deadline fires, children must be cancelled, and cancellation must be *cooperative at a tool boundary* rather than a thread kill, because a killed thread mid-`write_file` leaves a half-written file with no event-log record. Check the shared deadline before dispatching each tool call, not just at the top of the loop.

### Compaction triggers, and how they interact with tool-result truncation

The production design is a **cascade, cheapest first**, and Claude Code's five levels are the reference. Learn the shape and the thresholds; the point is the ordering principle, not the specific constants.

| Level | Trigger | Mechanism | Cost | Reversible |
|---|---|---|---|---|
| 1 · Tool-result budget | single result > 50,000 chars (`DEFAULT_MAX_RESULT_SIZE_CHARS`) | persist full output to disk, keep 2 KB preview + path in a `<persisted-output>` envelope | zero | yes (the file is there) |
| 2 · Snip | stale conversational scaffolding present | drop redundant wrappers/bookkeeping; feeds `snipTokensFreed` into the threshold calc | zero | no |
| 3 · Microcompact | cold: time gap > cache TTL (~5 min). hot: compactable tool-result count over threshold | cold path rewrites old tool results to `[Old tool result content cleared]`; hot path uses API-level `cache_edits` so the 100K+ cached prefix survives | zero API calls | no |
| 4 · Context collapse | ~90% window utilisation | projection-based folding, ~90% reduction; summaries live in a separate store and `projectView()` overlays them at query time | zero | **yes**, non-destructive |
| 5 · Autocompact | ~87% utilisation, and suppressed while collapse is active | fork a child agent, two-phase `<analysis>` then `<summary>` with 9 fixed sections; strip `<analysis>`, keep `<summary>` | one API call | **no** |

Five interactions that are the actual content of this section:

**1. Truncation changes the *rate*; compaction changes the *level*.** Truncating at the tool boundary is strictly higher leverage because it prevents the tokens from ever entering context, so compaction fires less often, so you make fewer irreversible summarizer calls. If your compaction rate is high, the bug is upstream. Fix the tool.

**2. Freeing tokens without updating the accounting makes the expensive level fire anyway.** This is the subtlest real bug in the cascade. The autocompact threshold is computed from the last assistant message's `usage`, which still reflects the *pre-snip* context size. If Level 2 freed 30K tokens and you do not subtract them, Level 5 fires on stale numbers and you pay for a summarizer call you did not need. Claude Code threads `snipTokensFreed` into the threshold calculation specifically for this. **The general rule: every cheap shaper must report how much it freed, and the trigger for every later shaper must be computed from the corrected number.**

**3. Compaction must preserve pointers, or Level 1 and Level 5 fight.** Level 1 replaced a 2.3 MB output with a preview plus a filesystem path. If Level 5's summarizer paraphrases that envelope into "the agent ran a search and found many results," the path is gone and the artifact is unreachable. Persisted-output envelopes, artifact paths, and open-items lists must be carried through compaction verbatim, in a preserved region, not summarized.

**4. Compaction fights the prompt cache, which is why the hot/cold split exists.** Any modification to old messages invalidates the cached prefix from that point forward. When the cache is already cold (user was away past the ~5-minute TTL) you may as well rewrite messages directly. When it is hot, holding 100K+ cached tokens, direct modification is a large cost hit, so the edit is expressed as API-level `cache_edits` that delete tool-result references server-side and leave the local message array untouched. The two paths are mutually exclusive and cold takes priority.

**5. Compaction needs a recovery step and a circuit breaker.** Recovery, because the immediate post-compaction failure is the agent re-reading files it just edited or making contradictory changes: restore the last ~5 recently-read files at ≤5K tokens each, restore activated skills at ≤25K tokens total, re-announce deferred tools and MCP directives, reset collapse state, restore plan mode. Circuit breaker, because compaction can fail repeatedly and pointlessly: Anthropic's March 2026 telemetry showed 1,279 sessions with 50+ consecutive autocompact failures, the worst hitting 3,272, wasting roughly 250,000 API calls per day globally. The fix was `MAX_CONSECUTIVE_AUTOCOMPACT_FAILURES = 3`. If the context is irrecoverably over limit, the fourth attempt fails too. **Any self-healing mechanism in a loop needs a breaker, or the fix becomes the new failure mode.**

**And the accounting precondition for all of it: anchor your token count on server-reported `usage`.** Pure client-side tokenizer estimation runs 30%+ error, which is enough to fire the cascade at the wrong time in both directions. Take the most recent API response's `usage` as ground truth and estimate only the messages added since; that gets under 5% without a tokenizer round-trip.

### The full stop-condition set

Nine, not six. Module 01 gave you the first six; these are the ones production adds.

| # | Stop | Fires when | Typical | Notes |
|---|---|---|---|---|
| 1 | Natural termination | model returns no tool call **and verification passes** | — | Unverified "done" is not a stop condition, it is a claim |
| 2 | Local step cap | this loop's iterations | 10-25 | |
| 3 | Tree step cap | iterations across all descendants | 3-6× local | Prevents fan-out multiplying your ceiling |
| 4 | Billed-token budget | cumulative paid tokens, run-wide | task-dependent | Not `context_tokens` |
| 5 | Cost budget | USD | 0.5-5.00 typical | The one that generates the incident when skipped |
| 6 | Wall-clock deadline | absolute monotonic timestamp | 30s-15min | Inherited absolutely by children |
| 7 | No-progress detector | no state delta over K steps, or identical `(tool,args)` N times | K≈4, N=3 | Intervene as a tool result, don't kill the run |
| 8 | Compaction circuit breaker | N consecutive compaction failures | 3 | Context irrecoverably over limit |
| 9 | External interrupt | user cancel, kill switch, policy revocation, parent cancellation | — | Must be cooperative at a tool boundary |

`stop_reason` is a first-class field on the run record, and the distribution of stop reasons is the single most useful agent dashboard you can build. Healthy looks like: mostly `verified_complete`, a small tail of `deadline` and `local_step_budget`, and near-zero `cost_budget` and `compaction_circuit_breaker`. `cost_budget` firing regularly means your budget is a load-bearing safety net rather than a backstop, which means you are one config change from an incident.

### Progress detection that actually works

Argument-hash repeat detection catches the dumbest loop. It misses the common one: the model *varies* its arguments slightly while making no progress. `search("clickhouse OOM")`, `search("clickhouse out of memory")`, `search("clickhouse memory error")` are three distinct hashes and zero progress.

Detect on **state delta**, in rough order of value:

```python
# untested sketch
def progress_signature(state) -> tuple:
    return (
        state.vcs.dirty_file_hashes(),      # did any file actually change?
        state.tests.passing_count,          # did the objective move?
        len([t for t in state.todos if t.done]),   # did a todo close?
        state.artifacts.count,              # was anything produced?
    )
```

Then three escalating interventions, all delivered as observations rather than exceptions:

1. **Nudge** at K=4 identical signatures: name the specific absence ("no file modified, no test outcome changed, no todo closed in 4 steps"), ask for the current hypothesis, and require a different approach. Naming the *evidence* is what makes this work; a generic "you seem stuck" gets a generic apology.
2. **Constrain** at K=7: shrink the tool registry for the next turn to the subset relevant to the phase. `statewright`'s result is the justification, local models going from 2/10 to 10/10 on a SWE-bench subset purely by shrinking the per-phase tool space.
3. **Escalate** at K=10: stop with `stop_reason="no_progress"` and hand off to a human with the trajectory, rather than burning the remaining budget.

Two additions worth knowing. **A monotone objective is the strongest progress signal available**, so create one if the task does not have one: passing-test count, lint-error count, unresolved-todo count. If it is flat for K steps, that is real evidence, not a heuristic. And **inject remaining budget into context** (`{"steps_left": 6, "seconds_left": 240, "usd_left": 1.20}`), because temporal awareness appears orthogonal to reasoning capability and explicit temporal feedback measurably improves deadline-constrained performance. An agent that knows it has six steps left triages; an agent that does not, explores.

### Loop invariants worth asserting

Assert these in the loop itself under a debug flag, and as unit tests against a scripted fake model. Every one corresponds to a bug class that is otherwise diagnosed from a 400 or a mysterious quality drop.

| Invariant | Violation symptom |
|---|---|
| `messages[0]` is byte-identical across iterations (or version-bumped deliberately) | Cache miss every turn; `cache_read_input_tokens ≈ 0`; cost 5-10× |
| Every `tool_use.id` has exactly one matching `tool_result` before the next model call | API 400 on malformed conversation, usually after a partial failure or cancellation |
| No two consecutive messages with the same role | API 400; usually a compaction or injection bug |
| `thinking` blocks are preserved when returning tool results | Silent multi-step reasoning degradation, no error |
| The original task and `open_items` survive every compaction | Turn-40 amnesia; agent abandons a pending obligation |
| Persisted-output paths and artifact references survive compaction verbatim | Agent loses access to a 2 MB output it needs; re-runs the expensive tool |
| `context_tokens` strictly decreases across a successful compaction | Compaction ran and freed nothing; you paid for a no-op |
| `billed_tokens`, `tree_steps`, `usd` are monotonically non-decreasing | You are counting a shrinking quantity as cost |
| `deadline_mono` is set once and never recomputed from `now()` | Deadline slips forever; run never times out |
| No tool executes after `stop_reason()` is non-null | Side effects after the run was supposed to have stopped |
| Idempotency key is stable across retries of the same `(run_id, tool, args)` | Duplicate tickets/emails after a retry |
| Replaying the event log to step *k* reproduces a byte-identical assembled request | Resume produces different behaviour than the original run; non-reproducible bugs |
| Every iteration emits exactly one span; the terminal one carries `stop_reason` | Missing runs in your dashboard, undercounted p99 |

The last one in the list is the one worth building first, because determinism is the precondition for resumability. If your context assembly reads a dict whose iteration order varies, or injects `datetime.now()`, or lists tools in set order, you cannot replay, you cannot snapshot-test, and you cannot bisect a regression.

### What to log at each iteration

One span per iteration, child spans per tool call, OpenTelemetry GenAI semantic conventions so it is portable. Per-iteration attributes:

```
run_id, parent_run_id, iteration, phase
model, model_version, reasoning_effort
prompt_prefix_hash          ← catches silent drift AND cache breakage
usage.input, usage.output, usage.cache_read, usage.cache_write
context_tokens_before, context_tokens_after
billed_tokens_cumulative, usd_cumulative
compaction: [levels_fired], tokens_freed_per_level, compaction_cost_usd
tool_calls: [{name, decision, validation_ok, latency_ms, bytes_in, bytes_out, persisted}]
progress_signature, steps_without_progress
transition_reason           ← which `continue` fired, by name
latency: ttft_ms, total_ms, tool_wall_ms, tool_cpu_ms
```

Per-run: `stop_reason`, total cost, total tree steps, max depth, compaction event count, denied-call count, verification outcome. Metrics to alert on: **p99 steps per run** (the mean hides runaways completely), **p99 cost per run**, **stop-reason distribution shift**, **compaction cost as a fraction of run cost**, and **denied-call rate by tool** (a spike is either a policy bug or an injection attempt). The two highest-value single fields are `prompt_prefix_hash` and `transition_reason`: the first makes prompt drift and cache breakage visible, the second turns "it looped" into "it took the `reactive_compact` transition 40 times."

### Making the loop resumable

Resumability is not "pickle the state." Three requirements:

**1. A typed append-only event log, not a message array.** Persist events, and derive messages from events:

```
user_message · assistant_message · tool_call · tool_result
approval_request · approval_result · plan_update · goal_update
skill_invocation · memory_load · context_compaction · connector_call
error · final_answer
```

Typed events give you replay, audit, compaction, evals, and debugging from one substrate. A message array conflates content with authority and loses everything that is not a message: the plan, the todo list, approval records, loaded instruction scopes, artifact paths, compaction summaries, connector scopes.

**2. Deterministic reconstruction.** `rehydrate(events[:k])` must produce byte-identical state to what existed at step *k*. That means: no `now()` in context assembly (pass a logical clock), stable ordering everywhere (sorted keys, ordered tool lists), version your prompt templates and record the version in the event, and store the *resolved* content of any file you injected, not just its path, because the file may have changed.

**3. Checkpoint boundaries chosen around side effects.** Checkpoint *after* appending the tool result, so a crash between execution and persistence is the only unsafe window, and make that window safe with idempotency keys: on resume, re-issuing the tool call with the same key returns the stored result rather than acting twice. Checkpoint *before* any `ask`-gated action, because that is the resume point a human approval returns to.

**Hibernate-and-wake, for tasks that exceed one context window.** This is the stronger requirement and the current frontier shape. The loop must be able to end deliberately, write a handoff artifact, and be resumed by a *fresh context* that never saw the earlier turns. Meta's Ranking Engineer Agent does this to resume interrupted 6-hour tasks across multi-day pipelines; Anthropic's pattern is an initializer agent that sets up the environment once and hands off to a coding agent that makes incremental progress each session, with feature lists, git commits, and test gates as the cross-session state. The design rule that falls out: **the handoff artifact must be sufficient on its own.** If resuming requires the previous context window, you have checkpointing, not hibernation. The test is brutal and simple: kill the process, start a fresh one, and see whether it makes progress.

---

## Build it from scratch

`(lab pending)` builds the controls against a scripted fake model and a fake clock, so every test is deterministic and free. The order matters:

1. **Fake clock and fake model first.** Everything after depends on being able to advance time and script responses.
2. **Nine stop conditions.** One test per condition asserting the exact `stop_reason`. Include the pair that people conflate: `local_step_budget` versus `tree_step_budget`.
3. **Hierarchical budgets with reservation.** The killer test: fan out three subagents in parallel against a parent with a $1.00 cap and assert total spend ≤ $1.00. Do it once without reservation to watch it fail at ~$3.00, then add reservation. This is the test that teaches the concept.
4. **Absolute deadline inheritance.** Three nested levels, each given a 10-second budget, assert the whole tree stops at 10 seconds not 30.
5. **Compaction cascade.** Implement all five levels with instrumented `tokens_freed`, then assert Level 5 does *not* fire when Levels 1-3 freed enough. Then break the accounting deliberately (don't subtract `snipTokensFreed`) and watch Level 5 fire on stale numbers.
6. **Compaction invariants.** Assert task, `open_items`, and persisted-output paths survive. Then implement post-compaction recovery and assert the last 5 read files are restored.
7. **Circuit breaker.** Force compaction to fail and assert the loop stops after 3 attempts with `stop_reason="compaction_circuit_breaker"` rather than looping.
8. **Progress detection.** Script a model that varies arguments while making no state change, prove hash-based detection misses it, then add `progress_signature` and prove it catches it at K=4.
9. **Verification gate.** Script a model that says "I've fixed it" with a red test suite. Assert the loop does *not* return `verified_complete`.
10. **Resumability.** Kill at step 7, resume from the event log, assert the assembled request at step 7 is byte-identical and that the mutating tool called at step 6 does not re-execute (idempotency key hit).
11. **Hibernate-and-wake.** Write a handoff artifact, start a *fresh process with no memory of the run*, and assert it makes progress.

Every one of these is a deterministic unit test. That is the point: the loop is the most testable part of an agent, and it is where most agent bugs live.

---

## How it's done in production

**Claude Code** is the most documented production loop. The numbers are worth memorising because they calibrate what "production loop" means: a 1,729-line async generator whose `while(true)` body spans 1,421 lines, with **9 distinct `continue` points**, each a named state transition (next tool call, reactive compact after 413, max-output-tokens recovery, stop-hook interruption, token-budget continuation, and more). It abandoned recursion for a state machine because the call stack blew up on long conversations. It checks the token budget **twice per iteration**, once before the model call (should we start?) and once after (did we exceed?). It runs the compaction cascade *before* every API call and the heavier autocompact check *after*, because microcompact is lightweight incremental cleanup and autocompact is heavyweight global compaction with different natural timing. Tool execution is streaming: tool 1 starts while the model is still generating tool call 3, and a 5-call turn goes from 30s sequential to 18s, a 40% latency win from architecture alone. And a detail that will save you a day: `stop_reason === 'tool_use'` is not reliably set, so detect tool calls by watching for `tool_use` blocks during streaming rather than trusting the stop reason.

**Microsoft Agent Framework** exposes the loop controls as configuration: a configurable iteration limit on the function-invocation loop; `MaxContextWindowTokens` + `MaxOutputTokens` to arm the token-budget-aware compaction strategy (and note: **compaction is silently disabled if you supply neither those nor a custom strategy**, which is a common "why did my long session die" cause); `LoopEvaluator` / `loop_should_continue` predicates with `loop_max_iterations` for the outer "keep going until done" loop, where the built-in `todos_remaining()` re-runs while the todo list has open items; and per-service-call history persistence so crash recovery and mid-run inspection work. The loop is applied as the outermost decorator, so each outer iteration is a complete, independently approved and traced run.

**LangGraph** models the loop as a graph with typed state, conditional edges, and checkpointers, which is the resumability requirement expressed as a framework. **LangChain's `AgentMiddleware`** gives you `before_model`, `wrap_model_call`, `wrap_tool_call`, `after_model` and friends, which is where loop-detection middleware, retry, fallback, and time-budget injection belong as cross-cutting concerns rather than inline `if`s.

### Failure-mode table

| Symptom | Cause | Fix |
|---|---|---|
| p99 run cost ≈ fanout × the configured cap, every subagent trace individually under budget | Check-then-spend on a shared budget; TOCTOU across parallel children | Reserve the child's maximum in the parent before dispatch; reconcile actuals on return |
| Nested run takes 3× the configured timeout | Deadline passed as a duration, so each level restarts the clock | Pass an absolute monotonic deadline; children inherit, never re-derive |
| Cost budget appears to *decrease* mid-run | Cost enforced against `context_tokens`, which compaction shrinks | Enforce against `billed_tokens`, monotonic and run-wide |
| Expensive autocompact fires immediately after a cheap snip freed 30K tokens | Threshold computed from stale `usage`; freed tokens not credited | Every shaper reports `tokens_freed`; later triggers use the corrected number |
| Agent re-runs an expensive tool it already ran; output "vanished" | Compaction paraphrased away the `<persisted-output>` path | Carry persisted-output paths, artifact refs, and open-items verbatim through compaction |
| Cost 5-10× estimate, `cache_read_input_tokens ≈ 0` | A mutating system prefix, or compaction rewriting old messages while the cache is hot | Freeze the static prefix at a sentinel boundary; use `cache_edits`-style API deletion on the hot path |
| ~250K wasted API calls/day; sessions with 3,000+ consecutive compaction attempts | Self-healing compaction with no circuit breaker | `MAX_CONSECUTIVE_COMPACTION_FAILURES = 3`, then stop and report |
| Agent re-reads files it just edited right after a long session compacts | No post-compaction recovery | Restore last ~5 read files (≤5K tokens each), skills (≤25K total), re-announce tools/MCP, restore plan mode |
| API 400 "invalid conversation" after a partial tool failure or cancellation | A `tool_use` without its matching `tool_result` | Assert 1:1 pairing before every model call; on cancellation, synthesize a `tool_result` saying "cancelled" |
| Multi-step reasoning quality degrades with no error | `thinking` blocks dropped when returning tool results | Preserve them; also note thinking mode cannot change mid-turn |
| Loop "gets stuck" but hash-based repeat detection never fires | Model varied arguments while making no progress | Detect on state delta (files changed, tests passing, todos closed), K≈4 |
| Agent reports success, tests are red, and the run is marked complete | Natural termination accepted without verification | Gate `verified_complete` on a deterministic check; unverified "done" continues or stops as `unverified_at_budget` |
| Resume produces different behaviour than the original run | Non-deterministic context assembly (dict order, `now()`, unstable tool ordering) | Snapshot-test the assembled request; pass a logical clock; sort everything |
| Compaction is 25% of run cost | Compacting instead of truncating at the source | Fix the tool: persist at ~50K chars with a 2 KB preview |

---

## Tradeoffs & when NOT to build this

- **Do not build a thick loop for a thin task.** If the task is 3 steps and read-only, a step cap and a deadline are sufficient and everything else is cost. The nine stop conditions, hierarchical budgets, and five-level compaction cascade are a response to *long* runs. Building them for a 3-step loop is the same mistake as building a distributed system for one server, and the tell in an interview is a candidate who recites the full apparatus without asking about task length.
- **Compaction is not free and it is often the wrong lever.** Levels 1-3 are genuinely cheap. Level 5 costs an API call, is irreversible, and loses information the model may need. If you are hitting Level 5 regularly, the fix is upstream: truncate tool results harder, externalize state to files the agent re-reads on demand, or shorten the task. State that survives compaction because it lives on disk is strictly better than state that must fit in the window.
- **Do not build durable execution if Temporal exists in your org.** Event log, deterministic replay, checkpointing, retries with idempotency, human approval that pauses for a day: that is a workflow engine, and you will build a worse one. Use Temporal or Step Functions with model calls as activities, and keep the LLM-specific parts (compaction, progress detection, verification) in your code. The honest split is that loop *policy* is yours and loop *durability* is a solved commodity.
- **Streaming tool execution buys latency and costs correctness surface.** The 40% win is real. So is the fact that cancellation, ordering, and partial-failure semantics get materially harder: a cancelled turn can leave a `tool_use` with no `tool_result`, which is an API 400 on the next call. Do it when latency is a product requirement, not by default, and only after your invariant assertions exist.
- **Do not let the model control compaction until your harness-controlled version is boring.** Agent-controlled compression is the better design in principle (it avoids interrupting a subtask mid-flight, and 22.7% token reduction with no accuracy loss is a real result) but it adds a failure mode where the model never calls the tool and you hit the wall anyway. Ship threshold-based first, add the tool second, keep the threshold as the backstop.
- **Budgets are a backstop, not a design.** If `cost_budget` is your most common `stop_reason`, your agent does not work and the budget is hiding it. The correct response is to reduce steps or improve tools, not to raise the cap. This is the single most common thing to get wrong at the organizational level, because raising a config value is easy and fixing a tool is not.

---

## Interview questions

### Q1 — Write me the production agent loop, with the controls.
**Testing:** whether you have owned a loop or read about one.
**Answer:** Ten stages per iteration, and name them as you write: shape context (cheapest-first cascade), pre-call gates (budgets, deadline, circuit breaker), inject remaining budget into context, call the model with streaming, error recovery (413 → reactive compact once, 429 → backoff against the deadline, 5xx → fallback model), post-call gates and stop hooks, natural-termination check *gated on verification*, execute tools through validate/permit/sandbox/shape, progress detection on state delta, checkpoint. Every `continue` carries a named transition reason.
**Follow-up trap:** *"Why check the budget twice in one iteration?"* Because the two checks answer different questions. Before the call: should we spend the next request at all, given what we have left? After: did this response push us over, and should we inject a "you have N steps left" nudge or stop? Claude Code does exactly this. Skipping the pre-call check means you always pay for one more request than your budget allowed, which at large output sizes is not a rounding error.

### Q2 — Three subagents run in parallel under a $1.00 run budget. Each stays under budget. Total spend is $2.90. What happened?
**Testing:** whether you see budget enforcement as a concurrency problem.
**Answer:** Time-of-check-to-time-of-use on a shared counter. All three children read `remaining = $1.00 - spent_so_far`, all three passed the check, all three spent. Check-then-spend is not safe under fan-out. The fix is **reservation**: the parent pessimistically debits each child's maximum from its own remaining budget *before dispatch*, hands the child a budget object capped at that reservation, and credits back `reservation - actual` on return. Because the debit happens once in the parent's thread before any child starts, no lock is needed. The diagnostic tell is exactly what you described: p99 run cost sitting at roughly `fanout ×` the cap while every individual subagent trace looks compliant.
**Follow-up trap:** *"What about steps and time, do they compose the same way?"* No, and this is where the answer gets interesting. Cost and billed tokens are additive and must be reserved. Steps need **two** counters, because a child's steps must not consume the parent's local cap (the parent would terminate early through no fault of its own) but must consume the run-wide tree cap (otherwise N children multiply your ceiling by N). And wall-clock is neither: it is inherited as an **absolute monotonic timestamp**, because passing a duration gives each nested level its own full timeout, so three levels of 600s becomes 1,800s.

### Q3 — Distinguish the token counts in your loop.
**Testing:** the distinction that makes budget bugs obvious, and most candidates have one number.
**Answer:** At least two, and they behave oppositely. `context_tokens` is what is in *this* agent's window right now: it drives compaction, it is per-agent, and it *decreases* when you compact. `billed_tokens` is everything the run has ever paid for, including every subagent's isolated context and every summarizer call: it drives cost, it is per-run, and it only increases. Compaction reduces the first and *increases* the second. So if you enforce a cost budget against `context_tokens`, compaction makes your spend appear to fall while you are paying more. Add a third if you care about caching: `cache_read` versus `cache_write` tokens, since they are priced differently and their ratio is your best single cache-health metric.
**Follow-up trap:** *"A subagent burned 120K tokens. How much did the parent's context grow?"* Roughly by the size of the returned summary, not 120K. Context isolation is the point of the subagent, and LangChain measures subagents processing 67% fewer tokens than skills in multi-domain scenarios for exactly this reason. But the run's bill grew by the full 120K plus any compaction the child performed. Isolation is a context property, not a cost property, and a dashboard with one line called "tokens" cannot express that.

### Q4 — Design the compaction trigger cascade.
**Testing:** whether "compaction" is one thing or a policy for you.
**Answer:** Five levels, cheapest first, four of them costing zero API calls. Level 1, tool-result budget: any single result over ~50K chars gets persisted to disk with a 2 KB preview and a path, so nothing is lost. Level 2, snip: drop stale conversational scaffolding, and critically report how many tokens you freed. Level 3, microcompact: clear old tool results by id, with two paths depending on cache state. Level 4, context collapse at ~90% utilisation: a non-destructive projection where summaries live in a separate store and are overlaid at query time, so it is reversible. Level 5, autocompact at ~87%: fork a summarizer, two-phase `<analysis>` then `<summary>`, keep only the summary, and it is irreversible. Collapse suppresses autocompact while active because they compete for the same token space and autocompact would destroy the finer-grained context collapse is preserving.
**Follow-up trap:** *"The cheap levels freed 30K tokens and autocompact fired anyway. Why?"* Because the autocompact threshold is computed from the last assistant message's `usage`, which still reflects the pre-snip context size. You freed tokens and did not tell the trigger. Claude Code threads `snipTokensFreed` into the threshold calculation specifically to fix this. The general rule: every cheap shaper must report `tokens_freed`, and every later trigger must compute from the corrected number. It is the most easily-missed bug in the cascade and it costs you an API call every time it fires.

### Q5 — What can compaction break that a naive implementation will not notice?
**Testing:** depth beyond "it might drop the task."
**Answer:** Five things. It can drop a pending obligation, so carry an explicit `open_items` list through every compaction. It can paraphrase away a `<persisted-output>` path, making a 2 MB artifact unreachable and causing the agent to re-run an expensive tool: persisted paths and artifact refs must be preserved verbatim, not summarized. It invalidates the prompt cache from the point of modification, which is why the hot path uses API-level `cache_edits` to delete tool-result references server-side while leaving the local message array untouched, preserving a 100K+ cached prefix. It launders authority: user instructions and untrusted tool results go through the same summarizer with no classification step, so an injected instruction in a project file survives compaction indistinguishable from legitimate context. And it causes immediate post-compaction confusion, so you need a recovery step: restore the last ~5 read files at ≤5K tokens each, restore activated skills at ≤25K total, re-announce deferred tools and MCP directives, restore plan-mode state.
**Follow-up trap:** *"Compaction keeps failing. What do you do?"* Circuit-break at 3 consecutive failures. If the context is irrecoverably over limit, the fourth attempt fails too. Anthropic's March 2026 telemetry: 1,279 sessions with 50+ consecutive autocompact failures, worst at 3,272, roughly 250,000 wasted API calls per day globally, fixed with `MAX_CONSECUTIVE_AUTOCOMPACT_FAILURES = 3`. The general principle is more useful than the constant: any self-healing mechanism inside a loop needs a breaker, or the fix becomes the new failure mode.

### Q6 — Your no-progress detector hashes `(tool, args)` and never fires, but the agent is clearly stuck. Why?
**Testing:** whether your progress detection is real or a heuristic you read about.
**Answer:** Because the model varies its arguments while making no progress. `search("clickhouse OOM")`, `search("clickhouse out of memory")`, `search("clickhouse memory error")` are three distinct hashes and zero forward motion. Detect on **state delta** instead: a tuple of dirty-file hashes, passing-test count, closed-todo count, artifact count. If that signature is unchanged for K≈4 steps, that is evidence. Then escalate in three stages, all as observations: nudge with the specific absence named ("no file modified, no test outcome changed, no todo closed in 4 steps") and ask for the current hypothesis; at K≈7 shrink the visible tool registry to the phase-relevant subset; at K≈10 stop with `stop_reason="no_progress"` and hand the trajectory to a human rather than burning the remaining budget.
**Follow-up trap:** *"What if the task has no natural progress metric?"* Create one, because a monotone objective is the strongest signal available and it is usually cheap. Passing-test count, lint-error count, unresolved-todo count, count of requirements with evidence attached. If you genuinely cannot construct one, that is itself important information: it means you also cannot verify completion, which means natural termination is an unverifiable claim, which means this task needs a human gate rather than autonomy.

### Q7 — Give me the complete stop-condition set and tell me which fires most in production.
**Testing:** whether module-01 knowledge got upgraded.
**Answer:** Nine. Verified natural termination; local step cap; **tree** step cap; billed-token budget; cost budget; absolute wall-clock deadline; no-progress detector; compaction circuit breaker; external interrupt (user cancel, kill switch, policy revocation, parent cancellation). Which fires most depends on your maturity, and that is the real answer: early on it is the no-progress detector, because the common failure is a stuck agent rather than infinite exploration. Once the agent works, healthy looks like mostly `verified_complete` with a small tail of `deadline` and `local_step_budget`. The distribution of `stop_reason` is the single most useful agent dashboard you can build.
**Follow-up trap:** *"`cost_budget` is our most common stop reason. Raise the cap?"* No. That means the agent does not work and the budget is hiding it. Budgets are backstops, not design. The fix is fewer steps or better tools: truncate tool results at the source, give the agent one good tool instead of three weak ones, cache aggressively, route simple turns to a smaller model. Raising the cap converts a bounded failure into an unbounded one, and it is the easiest wrong decision in the whole space because it is a one-line config change.

### Q8 — What loop invariants would you assert, and what does each one catch?
**Testing:** whether you can make a nondeterministic system testable.
**Answer:** Give five and their symptoms. `messages[0]` byte-identical across iterations, which catches cache breakage showing up as 5-10× cost with `cache_read_input_tokens ≈ 0`. Every `tool_use.id` has exactly one matching `tool_result` before the next model call, which catches the API 400 you get after a partial failure or a cancellation. `thinking` blocks preserved when returning tool results, which catches silent multi-step reasoning degradation that produces no error at all. Task statement, `open_items`, and persisted-output paths survive every compaction. And `context_tokens` strictly decreases across a successful compaction, which catches a compaction that ran, cost you a call, and freed nothing.
**Follow-up trap:** *"Which one would you build first?"* Determinism of context assembly: replaying the event log to step *k* must produce a byte-identical assembled request. It is first because it is the precondition for everything else. Without it you cannot snapshot-test, cannot resume correctly, and cannot bisect a regression. And it fails for boring reasons: a dict whose iteration order varies, a `datetime.now()` in the prompt, tools listed in set order, an injected file whose contents changed since the original run.

### Q9 — Make the loop resumable. Design it.
**Testing:** whether "checkpointing" is a word or a design.
**Answer:** Three requirements. A **typed append-only event log** rather than a message array (`user_message`, `assistant_message`, `tool_call`, `tool_result`, `approval_request`, `approval_result`, `plan_update`, `goal_update`, `context_compaction`, `error`, `final_answer`), with messages derived from events, because a message array loses the plan, the todo list, approval records, artifact paths, and loaded instruction scopes. **Deterministic reconstruction**, so `rehydrate(events[:k])` is byte-identical to the original step *k*: logical clock, stable ordering, versioned prompt templates recorded in the event, resolved file contents stored rather than paths. And **checkpoint boundaries chosen around side effects**: checkpoint after appending the tool result so the only unsafe window is between execution and persistence, and make that window safe with idempotency keys so a re-issued call returns the stored result instead of acting twice.
**Follow-up trap:** *"The task takes eight hours and exceeds one context window. Is checkpointing enough?"* No, you need hibernate-and-wake, which is a strictly stronger requirement: the loop must be able to end deliberately, write a handoff artifact, and be resumed by a *fresh context that never saw the earlier turns*. Meta's Ranking Engineer Agent does this for interrupted 6-hour tasks across multi-day pipelines; Anthropic's version is an initializer agent that hands off to a coding agent making incremental progress each session, with feature lists, git commits, and test gates as the cross-session state. The design rule: the handoff artifact must be sufficient on its own, and the test is to kill the process, start a fresh one, and see whether it makes progress.

### Q10 — Walk me through the reliability arithmetic. How much does each control actually buy?
**Testing:** whether your control list is justified or cargo-culted. This is the question that separates staff from senior.
**Answer:** Model it explicitly rather than hand-waving. Assume a task needing 12 productive steps, and decompose per-step failure into transient (tool 503, rate limit, flake) at 3.6%, semantic (wrong tool, wrong argument, bad plan) at 2.4%, and a context-degradation term that kicks in after roughly turn 8 without compaction. Then:

| Configuration | Model | Completion | Δ |
|---|---|---|---|
| A. Bare loop, exceptions propagate | p=0.90, `0.90^12` | **28.2%** | — |
| B. + errors-as-observations (transients recoverable in-turn) | p=0.94, `0.94^12` | **47.6%** | +19.4 pp |
| C. + no-progress detection | B, plus ~40% of stuck runs redirected instead of burning out | **~55%** | +7 pp |
| D. − compaction (show the cost of omitting it) | `0.94^8 × 0.85^4` | **31.8%** | −15.8 pp vs B |
| E. + checkpoint & resume, ≤2 retries at the failed step | transient collapses to `0.036³≈0`, so p=0.976, `0.976^12` | **74.7%** | +19.7 pp over C |
| F. + deterministic verifier | of E's 74.7% "completions", ~8 pp were false successes; verifier converts them to detected failures, one retry recovers ~5 pp | **~72% true-correct** (vs ~67% before) | +5 pp *correct*, −3 pp *reported* |

Three conclusions to state out loud. **Errors-as-observations and checkpoint-and-resume are the two big wins**, roughly +19 percentage points each, and they are the two cheapest things to build. **Compaction does not raise the ceiling; it removes a floor**, which is why its value is invisible on short tasks and decisive on long ones. And **the verifier makes your reported number go down and your real number go up**, which is the most important row in the table and the one people resist, because it means your dashboard gets worse when you improve the system.
**Follow-up trap:** *"Won't a better model just fix this?"* It moves p, and p is exponentiated, so it helps: 0.98 per step gives `0.98^12 = 78.5%` with no controls at all. But it does not help *structurally*, because the controls address failure classes a better model does not eliminate. A better model still hits a 503, still exceeds the context window at turn 40, still occasionally claims success on a red suite. And the empirical evidence points the other way on where to spend: LangChain moved a coding agent from rank 30 to top 5 on Terminal Bench 2.0 with harness-only changes and no model swap. Controls compose with model quality; they do not compete with it.

### Q11 — Streaming tool execution: yes or no?
**Testing:** whether you will take a latency win without pricing the correctness cost.
**Answer:** It is a real win, roughly 40%: a 5-tool-call turn goes from 30s sequential to 18s when tool 1 starts while the model is still generating call 3. Take it when latency is a product requirement. But price the cost honestly: cancellation, ordering, and partial-failure semantics get materially harder, and the specific failure is that a cancelled or partially-failed turn can leave a `tool_use` with no matching `tool_result`, which is an API 400 on the very next call. So the prerequisite is your invariant assertions, particularly 1:1 tool-use/tool-result pairing, plus synthesizing a "cancelled" tool result on the cancel path.
**Follow-up trap:** *"How do you know the model is done emitting tool calls, so you can start executing?"* Not from `stop_reason`. Claude Code's source comment is explicit that `stop_reason === 'tool_use'` is not always set correctly, so the reliable approach is to watch for `tool_use` blocks during streaming and treat the end of the content stream as the boundary. Depending on `stop_reason` for control flow is a good example of a loop bug that only shows up under load.

### Q12 — Your agent's p99 step count is 24 and the mean is 4. What is happening and what do you do?
**Testing:** whether you read the right statistic.
**Answer:** A bimodal distribution: most tasks finish quickly and a tail is hitting the step cap. The mean is useless here and this is why you alert on p99, not mean, for step count and cost. Diagnosis from traces: group the tail by `stop_reason` and by `transition_reason`. If the tail is `local_step_budget`, look at `progress_signature` in those runs; flat signatures mean the agent is stuck and the fix is progress detection plus better tools. If the tail is dominated by a single `transition_reason` like `reactive_compact`, the fix is upstream truncation. If the tail correlates with a specific tool's error rate, fix the tool. The general shape: the tail is a *different population*, so segment before you tune.
**Follow-up trap:** *"Just lower the step cap to 8."* That converts slow failures into fast failures, which is sometimes correct and is not a fix. It also silently drops the tasks that legitimately needed 15 steps, and you will not know because they now report `local_step_budget` rather than a wrong answer. Segment first: if the tail is stuck runs, cap-lowering is fine and progress detection is better. If the tail is genuinely harder tasks, you need task-dependent budgets, not a lower global cap.

### Q13 — What do you log per iteration?
**Testing:** whether your observability is designed or accreted.
**Answer:** One span per iteration with child spans per tool call, OpenTelemetry GenAI semantic conventions so it is portable. Per iteration: run and parent-run id, iteration number, phase, model and version and reasoning effort, **prompt prefix hash**, full usage breakdown including cache read/write, `context_tokens` before and after, cumulative billed tokens and USD, which compaction levels fired and how much each freed and what compaction cost, per-tool-call name/decision/validation/latency/bytes-in/bytes-out/persisted, `progress_signature` and `steps_without_progress`, **`transition_reason`**, and latency split into time-to-first-token, total, and tool wall time. Per run: `stop_reason`, totals, max tree depth, compaction event count, denied-call count, verification outcome.
**Follow-up trap:** *"If you could only add two fields, which?"* `prompt_prefix_hash` and `transition_reason`. The first makes the two most expensive silent bugs visible at once, unintended prompt drift and cache breakage. The second turns "it looped" into "it took the `reactive_compact` transition 40 times," which is the difference between a week of guessing and a ten-minute fix. Without `transition_reason`, a 9-continue-point loop is a black box even with full token accounting.

### Q14 — When would you not build any of this?
**Testing:** the senior signal.
**Answer:** Four cases. Short read-only tasks: a step cap and a deadline are sufficient, and the nine conditions plus five-level cascade are a response to *long* runs. Deterministic workflows: write the pipeline, since an elaborate loop maintaining a state machine an `if` expressed better is strictly worse. When Temporal or Step Functions is already in the org: event log, deterministic replay, checkpointing, idempotent retries, day-long human pauses is a workflow engine, and you will build a worse one; keep loop *policy* (compaction, progress detection, verification) and buy loop *durability*. And when a managed harness already ships it: Agent Framework's `HarnessAgent` gives you the iteration limit, compaction strategy, per-call history persistence, approvals, and OTel out of the box, so hand-rolling is only justified if you need a control it does not express.
**Follow-up trap:** *"Then why learn the internals at all?"* Because the failure modes are yours regardless of who wrote the loop. Agent Framework silently disables compaction if you supply neither token parameters nor a custom strategy, and the symptom is a long session dying at the context limit with "compaction enabled" in your config. You cannot debug that without knowing what the cascade is supposed to do. Frameworks change the implementation, not the physics.

---

## Red flags that fail you

- Only a step cap, or three budgets with no distinction between local and tree scope.
- One number called "tokens" doing duty for both compaction triggering and cost.
- Enforcing a cost budget against a quantity that compaction shrinks.
- Passing timeouts as durations to nested agents instead of an absolute deadline.
- Check-then-spend on a shared budget with parallel children.
- Treating compaction as one operation rather than a cheapest-first cascade.
- No `tokens_freed` reporting, so cheap shapers do not suppress expensive ones.
- Compaction with no post-compaction recovery and no circuit breaker.
- Accepting "no tool call" as completion with no deterministic verification.
- Progress detection that only hashes arguments.
- "Checkpointing" that means pickling a process.
- Alerting on mean step count instead of p99.
- No `transition_reason`, so a multi-continue loop is unobservable.
- Raising a cost cap in response to `cost_budget` being the top stop reason.
- Not knowing that `stop_reason === 'tool_use'` is unreliable.

## Cheat card

```
TWO TOKEN COUNTS (get this wrong and every budget bug follows)
  context_tokens  per-agent, in the window now  → drives COMPACTION, shrinks
  billed_tokens   per-RUN, everything ever paid → drives COST, only grows
  compaction lowers the 1st and RAISES the 2nd (summarizer call costs money)

BUDGET COMPOSITION ACROSS SUBAGENTS
  cost/tokens  additive + RESERVE before dispatch (check-then-spend = TOCTOU;
               N parallel children overshoot by up to N×)
  steps        TWO counters: local_steps (this loop) + tree_steps (whole run)
  deadline     ABSOLUTE monotonic timestamp, inherited. duration ⇒ 3 levels × 600s

9 STOP CONDITIONS
  verified natural term · local step cap · TREE step cap · billed-token budget
  cost budget · absolute deadline · no-progress · compaction circuit breaker
  external interrupt (cooperative, at a tool boundary)
  stop_reason distribution = your best dashboard
  cost_budget top reason ⇒ agent is broken, do NOT raise the cap

COMPACTION CASCADE (cheapest first; 4 of 5 cost zero API calls)
  1 tool-result budget  >50K chars → disk + 2KB preview + path      zero
  2 snip                stale scaffolding; MUST report tokens_freed  zero
  3 microcompact        cold: rewrite msgs (cache dead ~5min TTL)
                        hot:  cache_edits API-side, saves 100K+ prefix  zero
  4 context collapse    ~90% util, projection, REVERSIBLE            zero
  5 autocompact         ~87% util, fork summarizer, IRREVERSIBLE     1 call
  collapse ACTIVE ⇒ autocompact SUPPRESSED (they compete)
  freed tokens not credited to threshold ⇒ level 5 fires on stale usage
  post-compact recovery: last 5 files (≤5K ea) · skills (≤25K) · re-announce tools
  circuit breaker = 3   (1,279 sessions hit 50+ fails, worst 3,272, ~250K calls/day)
  token count: anchor on server `usage` + estimate delta → <5% err (vs 30%+ client)

PROGRESS = STATE DELTA, not arg hashes
  sig = (dirty_file_hashes, tests_passing, todos_closed, artifacts)
  K=4 nudge (name the absence) → K=7 shrink tool set → K=10 stop, escalate
  inject remaining {steps, seconds, usd} INTO context: temporal awareness is
    orthogonal to reasoning; it lets the model triage

INVARIANTS TO ASSERT
  messages[0] byte-stable      → else cache_read≈0, cost 5-10×
  1:1 tool_use ↔ tool_result   → else API 400 after partial failure/cancel
  thinking blocks preserved    → else silent reasoning degradation, no error
  task + open_items + persisted paths survive compaction
  context_tokens strictly ↓ after successful compaction
  replay(events[:k]) byte-identical  ← build this FIRST; precondition for resume
  no tool executes after stop_reason() is non-null

RESUMABLE
  typed append-only event log (not a message array) → derive messages from events
  deterministic rehydrate: logical clock, sorted everything, versioned templates,
    store RESOLVED file contents not paths
  checkpoint AFTER tool_result; idempotency key makes the gap safe
  HIBERNATE-AND-WAKE (task > 1 context window): handoff artifact must be
    sufficient alone. Test: kill process, fresh start, does it progress?

RELIABILITY MATH, 12 steps
  bare 0.90^12 = 28%  →  +errors-as-obs 0.94^12 = 48%  →  +no-progress ≈55%
  −compaction 0.94^8×0.85^4 = 32%   (compaction removes a FLOOR, no ceiling gain)
  +resume ≤2 retries, transient→0.036³: 0.976^12 = 75%   ← biggest single win
  +verifier: reported 75%→72% but TRUE-correct 67%→72%
  better model helps (0.98^12=79%) but does NOT remove 503s, turn-40 overflow,
    or false success claims

CLAUDE CODE REFERENCE NUMBERS
  1,729-line generator · 1,421-line while body · 9 named continue points
  budget checked TWICE per iteration (pre-call + post-call)
  streaming tool exec: 5 calls 30s → 18s (40%)
  stop_reason==='tool_use' is UNRELIABLE; watch for tool_use blocks

LOG PER ITERATION (top 2 fields: prompt_prefix_hash, transition_reason)
  alert on p99 steps + p99 cost (mean hides runaways), stop_reason shift,
  compaction cost as % of run cost, denied-call rate by tool

WHEN NOT TO
  short read-only task → step cap + deadline, done
  steps known → write the pipeline
  hours/days + exactly-once + day-long approvals → Temporal/Step Functions;
    keep loop POLICY, buy loop DURABILITY
```

## Sources

- [Claude Code Deep Dive Part 2: The 1,421-Line While Loop](https://harrisonsec.com/blog/claude-code-deep-dive-query-loop/) — 10 stages per iteration, 9 continue points, double budget check, streaming tool execution 30s→18s, unreliable `stop_reason`; accessed 2026-07-26
- [How Claude Code Compresses Context — The 5-Level Pipeline](https://harrisonsec.com/blog/claude-code-context-engineering-compression-pipeline/) — the five shapers with thresholds, `snipTokensFreed` accounting, hot/cold microcompact paths, post-compact recovery figures, autocompact circuit-breaker telemetry, token estimation error rates; accessed 2026-07-26
- [The Design Space of Today's and Future AI Agent Systems](https://arxiv.org/abs/2604.14228) — April 2026 reverse-engineering of Claude Code: five-stage progressive compaction, subagent permission rebuild, 27-event hook pipeline; accessed 2026-07-26
- [Compaction — Claude API docs](https://platform.claude.com/docs/en/build-with-claude/compaction) — server-side compaction; 84% token reduction on a 100-turn web-search eval; accessed 2026-07-26
- [Extended Thinking — Claude API docs](https://docs.anthropic.com/en/docs/build-with-claude/extended-thinking) — `budget_tokens`, and that thinking blocks must be preserved when returning tool results; accessed 2026-07-26
- [Prompt Caching — Claude API docs](https://docs.anthropic.com/en/docs/build-with-claude/prompt-caching) — `cache_control` breakpoint placement for multi-turn loops; accessed 2026-07-26
- [Agent Harnesses — Microsoft Learn](https://learn.microsoft.com/en-us/agent-framework/agents/harness) — iteration limit, `MaxContextWindowTokens`/`MaxOutputTokens` gating compaction, `LoopEvaluator`/`loop_should_continue`/`todos_remaining`, per-service-call history persistence; page updated 2026-07-08, accessed 2026-07-26
- [LangGraph — Low Level Concepts](https://langchain-ai.github.io/langgraph/concepts/low_level/) — the loop as a graph with typed state, conditional edges, checkpointing; accessed 2026-07-26
- [How Middleware Lets You Customize Your Agent Harness](https://blog.langchain.com/how-middleware-lets-you-customize-your-agent-harness/) — the six hooks; where loop-detection, retry, fallback, and budget injection belong; accessed 2026-07-26
- [Improving Deep Agents with Harness Engineering](https://blog.langchain.com/improving-deep-agents-with-harness-engineering/) — rank 30 → top 5 on Terminal Bench 2.0 with harness-only changes: verification loops, directory-map and time-budget context injection, loop-detection middleware, reasoning sandwich; accessed 2026-07-26
- [Autonomous Context Compression](https://blog.langchain.com/autonomous-context-compression/) — agent-controlled compression versus threshold-triggered; the mid-subtask interruption failure; accessed 2026-07-26
- [Active Context Compression: Autonomous Memory Management in LLM Agents](https://arxiv.org/abs/2601.07190) — 22.7% token reduction, no accuracy loss on long-horizon tasks; accessed 2026-07-26
- [Choosing the Right Multi-Agent Architecture](https://blog.langchain.com/choosing-the-right-multi-agent-architecture/) — subagents process 67% fewer tokens than skills in multi-domain scenarios; accessed 2026-07-26
- [Effective Harnesses for Long-Running Agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents) — initializer-then-coding-agent handoff; feature lists, git commits, test gates as cross-session state; accessed 2026-07-26
- [Ranking Engineer Agent (REA): Meta's Autonomous AI System for Ads Ranking](https://engineering.fb.com/2026/03/17/developer-tools/ranking-engineer-agent-rea-autonomous-ai-system-accelerating-meta-ads-ranking-innovation/) — hibernate-and-wake checkpointing for interrupted 6-hour tasks; accessed 2026-07-26
- [statewright](https://github.com/statewright/statewright) — phase-scoped tool constraint taking local models from 2/10 to 10/10 on a SWE-bench subset; accessed 2026-07-26
- [Real-Time Deadlines Reveal Temporal Awareness Failures in LLM Strategic Reasoning](https://arxiv.org/abs/2601.13206) — temporal awareness orthogonal to reasoning; explicit temporal feedback in the loop improves deadline-constrained performance; accessed 2026-07-26
- [A Scheduler-Theoretic Framework for LLM Agent Execution](https://arxiv.org/abs/2604.11378) — 70 open-source agent projects, 60% use the plain Agent Loop pattern; controllability/expressiveness/implementability trade-offs; accessed 2026-07-26
- [Hooks – Codex](https://developers.openai.com/codex/hooks) — `SessionStart`, `PreToolUse`, `PostToolUse` lifecycle hooks as deterministic loop governance; accessed 2026-07-26

## Changelog
- 2026-07-26 — created
