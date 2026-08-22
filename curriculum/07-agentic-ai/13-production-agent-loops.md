# Production Loops: Budgets, Resume, Kill Switches, Streaming

> **Track:** T07 Agentic AI · **Time:** 3.0h · **Prereqs:** none · **Updated:** 2026-08-01
> **Module id:** `T07-production-agent-loops` · **Tags:** production

## The 30-second version

A demo loop and a production loop run the same forty lines of message-passing; everything else is what you add so it survives contact with real traffic. Four things change: budgets move from "nice to have" to enforced-server-side-with-a-client-side-mirror, because a client-only check dies with the process; resume moves from "restart the run" to "resume from the last checkpoint," because at 85% per-step reliability a 10-step run only completes end-to-end about 20% of the time and re-running from scratch multiplies that failure; a kill switch moves from `Ctrl-C` to a cooperative flag checked at tool boundaries, because you cannot safely interrupt a tool mid-side-effect without either idempotency or a compensating action; and streaming moves from "print the final answer" to token-, step-, and event-level updates, because a user staring at a blank screen for 45 seconds files a support ticket regardless of whether the answer was correct. None of this is exotic engineering. It is the boring, unglamorous 80% of shipping an agent that a hackathon demo never needs.

## Why this gets asked

Because "I built an agent" and "I run an agent in production" describe wildly different amounts of engineering, and the interviewer has personally been paged at 3am for the gap between them: a run that silently died halfway and left a customer-facing record half-updated, a kill switch that didn't actually stop the LLM call so the bill kept climbing, a loop that looked fine in the demo and then hung for 90 seconds live because nothing streamed. They are checking whether you have actually operated one of these, not whether you can describe the loop.

---

## Lineage: past → present → future

**What came before.** Early agent deployments (2023) treated the agent loop like a synchronous function call: one HTTP request in, one blocking wait, one response out, exactly like calling any other model endpoint. That model breaks the moment a run takes longer than an HTTP timeout (typically 30-60s at a load balancer) or needs to survive a process restart. The first fix people reached for was just raising the timeout, which works until the run takes minutes and the caller has moved on, or the process crashes mid-run and the work vanishes with it. The pain that killed this approach was concrete: teams running overnight batch-style agent jobs discovered that a single dropped connection, deploy, or OOM meant total loss of a run that had done nine correct steps and failed on the tenth.

**Where it stands now.** The consensus split into two complementary layers. First, **durable execution**: agent state belongs in a database or event log, not in a process's memory, so a crash is a pause, not a loss (LangGraph's `PostgresSaver`, Temporal, Restate all express this). Second, **decoupled delivery**: the agent loop runs asynchronously (a worker, a queue, a session object) and the caller subscribes to a stream of events rather than blocking on one response — this is exactly the shape Anthropic's Managed Agents took (sessions + SSE event stream) and the shape most in-house harnesses converge on independently. The live disagreement is over granularity of checkpointing: checkpoint after every tool call (safest, most storage and latency overhead) versus checkpoint at coarser "phase" boundaries (cheaper, but a crash mid-phase repeats more work). Most production systems land on "checkpoint after every side-effecting tool call, not after every read-only one," which is a judgment call, not a settled rule.

**Where it's heading.** Two directions with different confidence. **Event-sourced agent state is winning** — treating the run as an append-only log of typed events (not a mutable message array) that both the resume path and the audit trail replay from is increasingly the default rather than a niche pattern; this is high confidence because it is now how the major managed platforms actually work internally. **Standardized cancellation semantics are still unsettled** — there is no cross-framework convention yet for what "kill this run" guarantees (does it wait for the in-flight tool call? does it roll back? does it just stop scheduling new steps?), and different frameworks answer this differently today. Treat any specific cancellation guarantee as framework-specific until you've checked, not as an industry standard.

---

## Mental model

```
DEMO LOOP                              PRODUCTION LOOP
──────────                             ───────────────
  request                                request
     │                                      │
     ▼                                      ▼
  ┌─────┐                          ┌─────────────────┐
  │ loop│ ── blocks until done     │  enqueue + return│ ── caller gets a run_id immediately
  └─────┘                          │  session/run id  │
     │                             └────────┬─────────┘
     ▼                                      │
  final answer                    ┌─────────▼─────────┐
                                  │   WORKER (loop)     │
                                  │  checkpoint after   │◄── crash here? resume from
                                  │  each side-effecting│    last checkpoint, not turn 0
                                  │  tool call          │
                                  └────────┬─────────┘
                                           │  emits events (token/step/budget)
                                  ┌────────▼─────────┐
                                  │  EVENT STREAM (SSE) │ ── caller subscribes, sees
                                  └────────┬─────────┘    progress in real time
                                           │
                          ┌────────────────┼────────────────┐
                          ▼                ▼                ▼
                    BUDGET GUARD    KILL SWITCH FLAG   RATE-LIMIT GATE
                 (checked pre+post   (checked at tool    (semaphore/token
                    each model call)     boundaries)         bucket)
```

The one thing to internalize: **a production loop is a durable worker with a subscription interface, not a function call.** Everything in this module is a consequence of that one shift — checkpointing exists because the worker can die, streaming exists because the caller isn't blocking synchronously, and the kill switch is cooperative because you can only safely intervene between the worker's atomic steps, not inside one.

---

## How it actually works

### Demo loop vs production loop, concretely

| Dimension | Demo | Production |
|---|---|---|
| Invocation | Synchronous call, block until done | Enqueue, return a run id, stream/poll for progress |
| Budget enforcement | A `for` loop with `range(10)` | Token, step, wall-clock, and cost budgets enforced server-side, mirrored client-side for UX |
| Failure recovery | Re-run from scratch | Resume from the last checkpoint |
| Cancellation | `Ctrl-C` kills the process | Cooperative flag, checked at tool boundaries, with idempotent tool calls |
| Visibility | Print statements | Structured event stream: token deltas, step boundaries, budget state, tool status |
| Concurrency | One request at a time on your laptop | N concurrent runs sharing a rate-limited upstream API, with backpressure |
| Idempotency | Not a concern — you notice if it double-sent an email | A mandatory property of every mutating tool, because retries and resumes will call it more than once |

### Budgets: where they're actually enforced

`T07-loop-engineering` covers the nine stop conditions and the budget-reservation pattern for nested subagents in depth — read that for the mechanics. The production-specific point is **where** the check lives:

```python
# untested sketch — illustrates enforcement layering, not a library
class Budget:
    def __init__(self, max_usd: float, deadline_ts: float):
        self.max_usd = max_usd
        self.deadline_ts = deadline_ts
        self.spent_usd = 0.0

    def check(self) -> str | None:
        if self.spent_usd >= self.max_usd:
            return "cost_budget"
        if time.monotonic() >= self.deadline_ts:
            return "deadline"
        return None

def run_step(budget: Budget, ...):
    # 1. CLIENT-SIDE pre-check: cheap, catches the common case before spending a request
    if (reason := budget.check()):
        return stop(reason)

    response = call_model(...)
    budget.spent_usd += price(response.usage)

    # 2. SERVER-SIDE mirror: the client check can be skipped by a bug, a race in a
    #    distributed worker pool, or a second process spending from the same budget.
    #    A shared counter (Redis INCRBYFLOAT, or a Postgres row with an UPDATE ...
    #    WHERE spent + delta <= max) is the source of truth; the client check is
    #    an optimization, not the enforcement.
    if not budget_ledger.try_spend(run_id, price(response.usage)):
        return stop("cost_budget")
```

**The failure mode this catches:** in-process budgets are per-process. If your loop runs as N replicas behind a load balancer, or a run gets retried onto a different worker, two processes each holding "the" budget object for the same logical run can each independently believe they have headroom and jointly overspend by up to Nx. The observable symptom is a cost anomaly where individual worker logs each show spend under the configured cap, but the billing dashboard shows total spend at N times the cap for that run — the same time-of-check-to-time-of-use bug covered for nested subagents in `T07-loop-engineering`, here caused by horizontal scaling instead of fan-out. The fix is the same idea: a shared, atomically-updated ledger is the actual enforcement point, and any in-process budget object is a fast-fail optimization layered on top.

### Durable resume: the arithmetic that makes it non-optional

At 85% per-step reliability, a 10-step run completes end-to-end `0.85^10 ≈ 20%` of the time (full derivation and the compounding-failure table live in `T07-agent-loop-from-scratch` and `T07-loop-engineering`). Two consequences that matter specifically for production operations:

1. **Without checkpointing, "20% completion" means 80% of runs are wasted work** — every failed run threw away everything it had already done correctly and forces a cold restart. With checkpointing, a transient failure (a 503, a timeout, a rate limit) resumes from the last saved state instead of turn zero, which is why `T07-langgraph-durable`'s worked reliability table shows checkpoint-and-resume as one of the two highest-leverage controls, worth roughly +19 percentage points of completion in that model.
2. **Checkpoint boundaries must sit around side effects, not around arbitrary turns.** Checkpoint *after* a tool result is durably recorded, before the next model call — that way a crash mid-model-call resumes by re-issuing a request that hasn't happened yet (safe), and a crash mid-tool-execution is the only genuinely hard case, which idempotency keys exist to solve (see below).

For the mechanics of checkpointers, `interrupt()`-based human-in-the-loop, and the state-machine implementation, see `T07-langgraph-durable` — this module assumes that machinery exists and focuses on what changes operationally once it does.

### Kill switches: stopping a running agent safely

This is the piece a demo never needs and production cannot ship without. The hard constraint: **you cannot forcibly interrupt an in-flight tool call without risking a half-completed side effect.** A `send_email` tool that gets killed after the SMTP call returns but before your code records "sent" will resend on the next resume unless it's idempotent. So kill switches are cooperative, not preemptive, with an escalation path for when cooperation fails:

```python
# untested sketch — cooperative cancellation with an escalation timeout
class KillSwitch:
    def __init__(self, run_id: str):
        self.run_id = run_id

    def requested(self) -> bool:
        # Backed by a shared store (Redis key, DB row, or a control-plane API) —
        # NOT an in-process boolean, because the request to kill usually comes
        # from a different process (an API call, an admin action) than the
        # worker that's running the loop.
        return kill_store.get(self.run_id) is not None

def run_loop(run_id: str, ...):
    kill = KillSwitch(run_id)
    for step in range(max_steps):
        # Checked BETWEEN steps — the safe boundary — never mid-tool-call.
        if kill.requested():
            checkpoint(run_id, status="cancelled")
            return

        response = call_model(...)
        if is_tool_call(response):
            # If the tool itself is slow (a long-running job, a big query),
            # the tool implementation must accept its own cancellation token
            # and check it internally — the harness can't reach inside a
            # black-box tool call to stop it.
            result = execute_tool(response, cancel_token=kill)
            checkpoint(run_id, result)  # durable before continuing
```

**Soft kill vs hard kill, and why you need both.** Soft kill sets the flag and waits for the current step to reach a safe boundary — this is the default and should resolve within one tool-call's latency, typically seconds. Hard kill (SIGKILL the worker process, or a platform-level "terminate container") is the escalation when soft kill doesn't resolve within a grace period — mirroring the SIGTERM-then-SIGKILL pattern container orchestrators use, commonly with a 30-second grace window. **Hard kill is not safe for correctness** — it can leave a tool call executed with no recorded result, which is why every mutating tool needs an idempotency key regardless of which kill path fires: the next attempt (a resume, a retry, or a human re-running the task) must be able to tell "did this already happen?" rather than blindly repeating it.

**The observable symptom of a kill switch that doesn't actually work:** the run's status flips to "cancelled" in your database, but the API spend and tool side effects continue for tens of seconds or minutes afterward — visible as billing activity or tool-side log entries with timestamps after the recorded cancellation time. That gap is exactly the time between "flag set" and "worker checks flag," and if it's large, your check interval is too coarse (e.g., checking only once per full loop iteration when a single tool call inside that iteration runs for 90 seconds).

### Streaming: what the user should see

Three granularities, and a production UI generally needs all three simultaneously:

| Level | What it is | Anthropic wire shape | UX purpose |
|---|---|---|---|
| **Token** | Incremental text as the model generates it | SSE `content_block_delta` with `text_delta` | Perceived latency — a wall of text appearing at once at 45s feels broken; the same text streamed in over 45s feels responsive |
| **Step** | A discrete unit of loop progress — one model turn, one tool call, one compaction | Your own event on top of the raw stream: `{"type": "step", "n": 4, "tool": "search", "status": "running"}` | Lets the UI show "Searching the web..." instead of a blank spinner, and lets a long-running tool report its own sub-progress |
| **Event** | Loop-level state changes: budget consumed, checkpoint saved, compaction fired, kill acknowledged | Custom events, not part of the raw model stream | Debuggability in production and, for agentic products, transparency ("47% of budget used") |

The raw Anthropic Messages API stream gives you token-level events natively (`message_start`, `content_block_start`, `content_block_delta`, `content_block_stop`, `message_delta`, `message_stop`) but says nothing about your loop's step or event structure — that's harness-level and you build it by wrapping the raw stream, tagging each chunk with which step/tool it belongs to, and interleaving your own synthetic events (budget updates, checkpoint markers) into the same channel the client consumes. Managed platforms that run the loop server-side (Anthropic's Managed Agents sessions, for instance) expose this as a single unified event stream for exactly this reason — the client shouldn't have to reconstruct step boundaries from raw token deltas itself.

**What breaks if you only stream tokens and not steps:** a five-tool-call turn where each tool takes 3-8 seconds looks, to a token-only client, like a single silent gap of 15-40 seconds between the last visible text and the next — because tool execution produces no text tokens. Users interpret silence as "hung," not "working," well before the actual timeout fires. Streaming step events (even just "using tool: search" with no content) during that gap is the fix, and it costs nothing at the model layer since it's harness-emitted.

### Concurrency and rate limits

A production system runs many loops concurrently against a rate-limited upstream (Anthropic's per-tier RPM/TPM/ITPM limits, or any provider's equivalent). Three mechanisms compose:

1. **A concurrency semaphore per upstream** bounds how many in-flight requests you allow at once, independent of the provider's rate limit — this protects your own connection pool and prevents one runaway workload from starving others.
2. **Respect `retry-after` on 429s** rather than a fixed backoff — the provider is telling you exactly how long to wait; SDKs generally retry 429/5xx automatically with exponential backoff (the Anthropic SDKs default to `max_retries=2`), but a saturated fleet needs this handled at the fleet level too, not just per-request, or every worker backs off independently and you get a synchronized retry storm (see `T21-resilience-catalogue` for the general pattern — full jitter, retry budgets).
3. **Parallel tool calls within one turn** are a separate axis from cross-run concurrency: a single assistant turn can contain multiple `tool_use` blocks, and the model expects all their results back in one user message. Execute them concurrently (they're independent by construction — the model asked for them in the same turn), but a failed tool in the batch still needs a `tool_result` with `is_error: true` for every one of them; you cannot silently drop the failed one and return only the succeeded results, or the next model call is malformed (every `tool_use` id needs exactly one matching `tool_result`).

**The observable symptom of a runaway loop, and how you detect it before the bill does:** the textbook failure is a loop that keeps calling the same tool with near-identical arguments because it's making no real progress (covered in depth in `T07-loop-engineering`'s no-progress detector). Operationally, you don't want to discover this from the invoice. Instrument and alert on: step count per run (alert on p99, not mean — a bimodal distribution where most runs finish in 3 steps and a tail hits the cap hides in an average), cost per run compared to a rolling baseline, and time-to-first-token per step (a step that used to take 2s and now takes 40s is a symptom of upstream degradation or context bloat, not something you want a customer to report first).

---

## Build it from scratch

There is no separate lab for this module — it composes the loop from `(lab pending)`, the budget and checkpoint machinery from `T07-loop-engineering` and `T07-langgraph-durable`, and adds exactly two new pieces on top: a kill-switch check at the tool boundary (shown above) and an event-stream wrapper that tags each chunk of the raw model stream with step metadata before forwarding it to the client. Building those two on top of an already-working checkpointed loop is a half-day exercise, not a from-scratch build — which is itself the point: production-readiness is additive layers on the same forty-line core, not a different architecture.

---

## How it's done in production

**Framework/platform map:** LangGraph gives you checkpointers and `interrupt()`-based HITL but you still own the event-stream shaping for your client. Anthropic's Managed Agents runs the loop server-side entirely and gives you sessions with a built-in SSE event stream, `user.interrupt` for cancellation, and compaction — trading control for not having to build any of this yourself. Temporal/Restate give you the strongest durability guarantees (workflow-as-code with automatic replay) at the cost of adopting a full workflow engine. Raw, hand-rolled loops are still common and reasonable when the concurrency and durability requirements are modest.

**What breaks at scale**

| Symptom | Cause | Fix |
|---|---|---|
| Billing shows Nx the configured per-run cap | Budget enforced only in-process, run scaled across N workers/retries | Shared, atomically-updated budget ledger (Redis/Postgres), client check as fast-fail only |
| A "cancelled" run keeps spending money for tens of seconds | Kill flag checked too coarsely (once per full loop iteration instead of at sub-step boundaries) | Check the kill flag between the model call and tool execution, not just between full steps; escalate to hard kill after a grace period |
| Client reports the agent "hung" during a multi-tool-call turn | Only token-level streaming; tool execution produces no visible output | Emit step-level events ("using tool: X") during tool execution, not just text deltas |
| Resumed run duplicates a side effect (double email, double charge) | Tool call retried/resumed without an idempotency key | Client-generated idempotency key per mutating tool call; server stores `(key → result)` |
| API 400 "invalid conversation" after a partial failure | A `tool_use` block has no matching `tool_result` after a kill/crash mid-turn | Synthesize an error `tool_result` for every pending `tool_use` before checkpointing a partial turn |
| Fleet-wide retry storm right as the upstream starts recovering | Every worker backs off independently with no shared retry budget | Fleet-level retry budget (cap retries at ~10-20% of total request volume), full jitter per `T21-resilience-catalogue` |
| p99 step count is 10x the mean | A tail of stuck runs hitting the step cap while most runs finish fast | Alert on p99, not mean; segment the tail by stop_reason to find the systemic cause |

---

## Tradeoffs & when NOT to use this apparatus

- **Short, synchronous, single-user tasks don't need any of this.** A 3-step tool loop answering one interactive request in under 10 seconds doesn't need durable checkpointing, a kill switch, or a distributed budget ledger — a step cap and a deadline are enough, and building the full production apparatus for it is pure overhead. Reach for this module's machinery once runs are long enough, numerous enough, or high-stakes enough that a crash or a runaway actually costs something.
- **If you already have a workflow engine (Temporal, Step Functions) in the org, don't reinvent checkpointing and resume on top of a raw loop.** Event log, deterministic replay, and durable retries are exactly what those systems already provide; wrapping an LLM call as an activity inside one of them is usually less code than building bespoke checkpoint/resume logic, and it comes with the operational tooling (dashboards, replay debugging) you'd otherwise build yourself.
- **A managed agent platform is the right call when you don't want to own the harness at all** — if the team doesn't want to build and maintain streaming infrastructure, checkpointing, and cancellation semantics, that's a legitimate reason to pay for a platform that provides them, not a sign of laziness. The tradeoff is control: you inherit the platform's cancellation guarantees and event shapes as given.
- **Don't add a kill switch that can't actually stop spend.** A kill switch that only stops scheduling new model calls but doesn't cancel an in-flight streaming request is worse than no kill switch, because it gives operators false confidence that they've stopped the bleeding. If you can't cancel an in-flight request at the transport layer, say so explicitly in your runbook rather than let people assume "cancel" means "cancel now."

---

## Interview questions

### Q1 — What actually changes between a demo agent loop and a production one?
**Testing:** whether the candidate has operated one, not just built one.
**Answer:** The forty-line loop itself barely changes. What changes is everything wrapped around it: budgets move from a `for` loop bound to enforced, shared, server-side limits; failure recovery moves from restart-from-scratch to resume-from-checkpoint; cancellation moves from `Ctrl-C` to a cooperative flag checked at safe boundaries; and output moves from a single blocking response to a multi-granularity event stream. Concurrency and idempotency also become mandatory rather than implicit, because production runs many loops at once and retries/resumes will call tools more than once.
**Follow-up trap:** *"Give me a concrete failure you'd hit if you skipped just one of those."* — pick a specific one and its specific symptom, e.g. skipping durable resume means a process crash after 9 correct steps discards all of them and the customer waits twice as long for a re-run that might fail differently the second time. A vague "it would be less robust" fails this question; naming the exact observable symptom passes it.

### Q2 — Why is a client-side budget check not sufficient in production?
**Answer:** It's per-process. If a run scales across multiple workers, or gets retried onto a different worker after a failure, each process independently believes it holds the authoritative remaining budget, and N processes can each spend up to the cap, jointly overspending by up to Nx. The client-side check is a legitimate fast-fail optimization — it avoids paying for a request you already know is over budget — but the actual enforcement point has to be a shared, atomically-updated ledger (a Redis counter, a database row with a conditional update) that every process reads and writes to.
**Follow-up trap:** *"Your ledger update and your API call aren't atomic together — what's the race?"* — you can spend from the ledger, then the API call fails or is retried, and now you've decremented budget for work that didn't happen (or happened twice). The fix is the reservation pattern: debit the maximum possible cost before the call, then credit back the difference after, so a failure mid-flight doesn't silently claim budget it never used, and a legitimate retry can't double-spend because the reservation already accounted for the worst case.

### Q3 — Why does an un-checkpointed 10-step agent at 85% per-step reliability complete only about 20% of the time, and what does checkpointing actually fix?
**Answer:** Reliability compounds multiplicatively across steps: `0.85^10 ≈ 20%`. Without checkpointing, every failure — no matter which step it happens on — throws away all prior correct work and forces a restart from step zero, so the *effective* completion rate for the logical task (get it right end to end, however many attempts it takes) stays low and each attempt is expensive. Checkpointing doesn't change the per-step reliability number; it changes what a failure costs. A transient failure resumes from the last durably-saved state instead of from scratch, so a failure at step 7 loses one step's worth of work, not seven.
**Follow-up trap:** *"So checkpointing raises the 85% number?"* — no, and conflating the two is the wrong answer. Checkpointing raises effective completion rate by cutting the cost of retrying, not by making any individual step more reliable. Raising the actual per-step reliability requires errors-as-observations, better tools, or a better model — orthogonal fixes that compose with checkpointing rather than substitute for it.

### Q4 — How do you stop a running agent safely mid-tool-call?
**Answer:** You generally can't, safely, mid-call — you can only stop it at the boundary between calls. The kill switch is a cooperative flag stored somewhere shared (not in-process, since the kill request usually comes from a different process than the worker), checked between the model call and tool execution. On a kill, checkpoint the run as cancelled and stop scheduling new steps. If a tool call is already in flight and slow, the tool implementation itself needs to accept a cancellation token and check it internally — the harness cannot reach inside a black-box call to abort it. Escalate to a hard kill (terminate the worker process) only after a grace period, mirroring SIGTERM-then-SIGKILL.
**Follow-up trap:** *"What if the tool already executed but you killed it before recording the result?"* — that's exactly why every mutating tool needs an idempotency key regardless of the kill path. A hard kill can leave a side effect with no recorded outcome; the resume or retry that follows must be able to check "did this already happen" via a stored `(key → result)` rather than blindly re-executing.

### Q5 — Design the event stream a client should consume for a long agent run.
**Answer:** Three layers, wrapped around the raw model stream: token-level deltas (forwarded largely as-is from the provider's SSE stream — `content_block_delta` events) for perceived responsiveness during generation; step-level events you synthesize yourself (`{"type": "step", "tool": "search", "status": "running"}`) so the UI shows activity during tool execution, which produces no text tokens and would otherwise look like a hang; and loop-level events for budget consumed, checkpoint saved, and compaction fired, for both UX transparency and debuggability. All three should share one channel so the client doesn't have to reconstruct step boundaries by inference from raw token timing.
**Follow-up trap:** *"Your five-tool-call turn takes 20 seconds and users report it as 'hung.' Diagnose."* — token-only streaming. Tool execution between text generation produces no tokens, so a client watching only text deltas sees silence for the full duration of tool execution, and users interpret silence as broken well before any actual timeout. Adding step events during exactly that gap fixes it at zero cost to the model call.

### Q6 — Your fleet is retrying against an upstream that's recovering from an outage, and it just got slower to recover, not faster. What happened?
**Answer:** Classic retry amplification without a fleet-level budget — the same failure mode covered generally in `T21-resilience-catalogue`, specific here to a fleet of agent loops rather than a single service call. Every worker independently backs off and retries on its own schedule; without jitter, retries synchronize into waves that hit the recovering service exactly as it comes back up, and without a shared retry budget, aggregate retry volume can be a large multiple of legitimate traffic even though each individual worker looks well-behaved.
**Follow-up trap:** *"Respecting `retry-after` should fix this — why doesn't it?"* — `retry-after` tells one caller how long to wait, but doesn't coordinate across your fleet; if 500 workers all respect the same `retry-after` value, they all retry at the same moment. You need jitter on top of the provider's guidance, and ideally a fleet-level retry budget (cap retries at some fraction of total request volume) so the aggregate behavior is bounded regardless of how many individual workers are retrying.

### Q7 — Multiple tool calls come back in one model turn. One of them fails. What do you send back?
**Answer:** A `tool_result` for every `tool_use` block in that turn, including an error result (`is_error: true`) for the one that failed — never silently omit it. The API pairs `tool_use` and `tool_result` by id, and a turn with an unpaired `tool_use` produces an invalid next request. Execute the independent calls concurrently since the model issued them together expecting parallel execution, but the failure of one doesn't excuse you from reporting on all of them.
**Follow-up trap:** *"Your loop crashed mid-execution of that batch, and only two of the three tool calls finished before the crash. What does your resume logic do?"* — before the resumed run can proceed, it must synthesize an error or cancelled `tool_result` for the third, unfinished `tool_use`, or the next model call is malformed. This is the same 1:1 pairing invariant, just triggered by a crash instead of a business-logic failure — checkpointing partial turns needs to account for it explicitly.

### Q8 — When would you NOT build this production apparatus?
**Testing:** the senior "when not to" signal.
**Answer:** For short, synchronous, single-user tasks that finish in a few seconds with a handful of tool calls — a step cap and a deadline are sufficient, and durable checkpointing, a distributed kill switch, and a shared budget ledger are pure overhead relative to the risk. Also skip building it yourself if the org already runs a workflow engine (Temporal, Step Functions): checkpointing, deterministic replay, and durable retries are exactly what those provide, and reimplementing them on a raw loop produces a worse version of something you already have. And if a managed agent platform already runs the loop server-side with sessions, streaming, and cancellation built in, paying for that instead of building it is a legitimate choice, not a shortcut.
**Follow-up trap:** *"Your team built the full apparatus for a 3-step synchronous chatbot. Do you rip it out?"* — measure before deciding. If telemetry shows the step count is consistently low and runs never approach the timeout, the machinery is dead weight and simplifying reduces both latency and operational surface area with no loss. But if you can't show that from data, don't rewrite on taste; that's the same over-engineering-vs-under-engineering judgment call that shows up across this whole track, and getting it right requires evidence either direction.

### Q9 — What's the difference between checking a budget and reserving a budget, and why does it matter under concurrency?
**Answer:** Checking asks "do I have headroom right now?" and spends optimistically; reserving debits the maximum possible cost of the next operation *before* it runs, then credits back the unspent difference afterward. Under concurrency, checking is a time-of-check-to-time-of-use bug: two processes can both check, both see headroom, and both spend, together exceeding the cap. Reserving closes that window because the debit happens atomically before either process proceeds, so the second process to reserve sees the first process's reservation already reflected in the ledger.
**Follow-up trap:** *"Doesn't reservation waste budget if the actual cost comes in under the reserved maximum?"* — temporarily, yes, and that's the correct tradeoff: a reservation that's too generous under-utilizes budget for a moment; a check that's too optimistic over-spends permanently. Credit back the unspent portion immediately after the operation completes so the window of over-reservation is as short as one operation's latency, not the whole run.

### Q10 — Walk me through what "streaming" means at each of the three levels you'd instrument, and why a production system needs all three rather than just one.
**Answer:** Token-level streaming (raw SSE deltas from the model) solves perceived latency during generation — the same total wait feels much shorter when text appears incrementally. Step-level streaming (harness-synthesized events marking tool calls and their status) solves the silence problem during tool execution, which produces no text tokens at all and would otherwise look identical to a hang. Event-level streaming (budget state, checkpoints, compaction) solves transparency and debuggability, both for end users in agentic products and for operators diagnosing a run after the fact. Any one alone leaves a gap: token-only misses tool-execution silence, step-only misses generation latency, and neither gives you the operational visibility event-level streaming does.
**Follow-up trap:** *"Which one would you cut first under a tight timeline?"* — event-level, if forced to cut one, because it's primarily an internal/debugging concern and its absence doesn't degrade the immediate user-facing experience the way losing token or step streaming would. But say explicitly that cutting it trades away your ability to diagnose the exact failures this whole module is about, so it should come back quickly, not stay cut.

---

## Red flags that fail you

- Describing "production-ready" as just adding a try/except around the loop.
- Claiming a kill switch stops spend instantly with no mention of the cooperative-check gap.
- Enforcing budgets only in-process with no answer for horizontal scaling.
- Streaming only text tokens and calling that "real-time" with no plan for tool-execution silence.
- Not knowing that resumed or retried tool calls need idempotency keys.
- Treating "add checkpointing" as raising per-step reliability rather than lowering the cost of a failure.
- No answer for what happens to unpaired `tool_use` blocks after a crash mid-turn.
- Reaching for the full production apparatus on a 3-step synchronous chatbot with no data to justify it.

---

## Cheat card

```
DEMO -> PRODUCTION
  sync call, block          -> enqueue + return run_id, stream progress
  in-process budget         -> shared atomic ledger (client check = fast-fail only)
  restart on failure        -> resume from last checkpoint (after side effects, before next call)
  Ctrl-C                    -> cooperative kill flag, checked AT TOOL BOUNDARIES only
  print statements          -> token + step + event streaming, one channel

RELIABILITY MATH: 0.85^10 ~= 20% completion uncheckpointed
  checkpointing lowers COST OF FAILURE, does not raise per-step reliability

BUDGET RESERVATION (fixes TOCTOU under concurrency/scale)
  debit max-possible BEFORE the call -> credit back unspent AFTER
  plain "check then spend" overshoots by up to Nx under N concurrent workers

KILL SWITCH
  soft: cooperative flag, resolves within one tool call's latency
  hard: escalate after grace period (SIGTERM -> SIGKILL analog, ~30s typical)
  EVERY mutating tool needs an idempotency key regardless of kill path

STREAMING (need all three, not one)
  token  -> SSE content_block_delta, perceived latency during generation
  step   -> harness-synthesized ("using tool: X"), fixes silence during tool exec
  event  -> budget/checkpoint/compaction state, debuggability + transparency

CONCURRENCY
  per-upstream semaphore (protect your pool) + respect retry-after + fleet retry budget
  parallel tool_use in one turn: ALL tool_use ids need a matching tool_result,
    even the failed ones (is_error: true) -- never omit

RUNAWAY DETECTION: alert on p99 step count and cost per run, not the mean
  (bimodal: most runs fast, a tail hits the cap and hides in an average)

WHEN NOT TO BUILD THIS: short sync single-user tasks; org already has
  Temporal/Step Functions; a managed agent platform already runs the loop
```

## Sources

- [Claude Platform Docs — Streaming messages](https://platform.claude.com/docs/en/build-with-claude/streaming) — SSE event types (`message_start`, `content_block_delta`, `message_delta`, etc.) — accessed 2026-08-01
- [Anthropic — Building Effective Agents](https://www.anthropic.com/engineering/building-effective-agents) — accessed 2026-08-01
- [Anthropic Managed Agents — Sessions & Events](https://platform.claude.com/docs/en/managed-agents/events-and-streaming) — session lifecycle, `user.interrupt`, event stream shape — accessed 2026-08-01
- [Error handling in distributed systems: a guide to resilience patterns — Temporal](https://temporal.io/blog/error-handling-in-distributed-systems) — durable execution and checkpoint boundaries — accessed 2026-08-01
- [Anthropic API rate limits](https://platform.claude.com/docs/en/api/rate-limits) — retry-after, RPM/TPM tiers — accessed 2026-08-01

## Changelog
- 2026-08-01 — created
