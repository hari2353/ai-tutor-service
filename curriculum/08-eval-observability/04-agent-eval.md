# Trajectory Eval, Tool-Call Accuracy, Task Completion, Cost/Step

> **Track:** T08 Eval & Observability · **Time:** 2h · **Prereqs:** `T08-llm-as-judge`
> **Module id:** `T08-agent-eval` · **Tags:** sprint, eval, agents

## The 30-second version

Outcome-only eval ("did the final answer look right") is insufficient for agents because an agent can reach the right answer via a path that will fail tomorrow — wrong tool, lucky retry, or a route that burns 10x the budget — and outcome eval can't see any of that. Real agent eval scores the trajectory: did it call the right tools with correct arguments, did it complete the task by the actual end-state check (not just plausible-looking output), and did it do so within a reasonable step count and cost. Frontier agents on realistic multi-turn benchmarks like tau-bench succeed on well under half of tasks and are inconsistent across repeated attempts on the *same* task — pass^8 (all 8 of 8 retries succeeding) drops below 25% in retail-domain tasks even for capable models — so you have to treat agent results as a distribution, not a single pass/fail, and your CI gates have to be built around that distribution or they will flake constantly.

## Why this gets asked

Because the interviewer has shipped an agent that looked great on a demo and a curated eval set, then failed in production in a way the eval never would have caught — it called the right tool with a subtly wrong argument, or it "succeeded" by returning a plausible-sounding answer that didn't match what the backend actually did. They want to know if you'll build eval that inspects the *path*, not just the destination, and whether you understand that an agent's nondeterminism means a single run proves nothing — you need pass^k thinking and a CI gate that doesn't cry wolf on every PR.

---

## Lineage: past → present → future

**What came before.** Early LLM eval inherited directly from single-turn NLG eval: give the model a prompt, score the output against a reference or a judge, done. This is exactly the outcome-only model, and it worked reasonably for single-shot QA and summarization. As soon as teams wrapped LLMs in tool-calling loops (2023 onward — ReAct, function calling, early LangChain agents), outcome-only eval kept being applied out of habit, and it silently missed the actual failure surface: an agent that calls `create_refund(amount=500)` instead of `create_refund(amount=50)` and then writes a summary claiming success looks identical to a correct run under an outcome-only judge that only reads the final text. The pain that killed this approach was operational, not academic — teams discovered wrong-argument tool calls and silent partial failures in production logs that their eval suite had rated as "pass."

**Where it stands now.** The consensus is a multi-layer eval: (1) tool-call accuracy — binary, did it call the right tool with the right arguments, checked against ground truth or a verifier function, not a judge's opinion; (2) trajectory evaluation — did the sequence of steps constitute a reasonable path, scored either against golden trajectories (exact or fuzzy match) or by an LLM judge reading the full trace; (3) task completion — checked against actual end state (did the database row change, did the email get sent), not the agent's self-reported summary; (4) cost and steps per task as first-class metrics tracked alongside accuracy, because an agent that "succeeds" by taking 40 steps and $2 of tokens per task is not shippable even if its success rate is high. Benchmarks like tau-bench (and its successor tau2-bench) formalized this with realistic multi-turn tool-and-user-simulation tasks and introduced the pass^k metric specifically to force teams to confront nondeterminism: reporting pass^1 (any success in one try) hides the fact that pass^8 on the same task can be dramatically lower. The live disagreement is where the LLM-judge layer should sit — some teams judge the full trajectory holistically with an LLM (catches things deterministic checks can't, like "did the agent use unnecessarily rude language on a tool-failure recovery"), others insist on decomposing everything into deterministic per-step checks because a judge grading a multi-thousand-token trace has its own reliability ceiling (see `T08-llm-as-judge`) and adds a second source of eval-noise on top of the agent's own noise.

**Where it's heading.** Durable execution frameworks (Temporal, LangGraph checkpointers) are increasingly treated as part of the eval story, not just the runtime story — because if a run is checkpointed, you can replay from any intermediate state to isolate exactly which step diverged from the golden trajectory, rather than re-running the whole task from scratch. This is real and shipping. Golden-trajectory tooling is moving toward semi-automated construction (recording real successful production runs, then having humans lightly edit them into canonical goldens rather than authoring from scratch) — moderate confidence, actively being built. More speculative: standardized cost-aware benchmark leaderboards (reporting a Pareto frontier of accuracy vs. cost-per-task rather than accuracy alone) are being discussed but not yet the norm; expect this to solidify as agent inference costs become a board-level concern.

---

## Mental model

```
                         one agent run = one TRAJECTORY

  user goal ──▶ [step 1: tool call] ──▶ [step 2: tool call] ──▶ ... ──▶ final state
                     │                        │
                     ▼                        ▼
              TOOL-CALL ACCURACY        TOOL-CALL ACCURACY
              right tool? right args?   right tool? right args?
              (binary, per call)        (binary, per call)

  ──────────────────────────────────────────────────────────────────▶
                     the WHOLE PATH above is the TRAJECTORY
                     scored against a golden trajectory or an
                     LLM judge reading the full trace:
                     - reasonable route? (not necessarily identical,
                       but not wasteful/wrong either)
                     - correct error recovery?

  ──────────────────────────────────────────────────────────────────▶
                                                    │
                                                    ▼
                                          TASK COMPLETION
                                    checked against ACTUAL END STATE
                                    (DB row, sent email, file written) —
                                    NEVER the agent's own summary text

  cost/steps tracked ALONGSIDE every metric above, every run:
  $ per task, tokens per task, steps per task, wall-clock per task

  repeat the SAME task N times (pass^k):
  pass^1 = 78%  ─┐
  pass^4 = 51%   ├─ nondeterminism means a single run proves nothing
  pass^8 = 23%  ─┘
```

---

## How it actually works

### Why outcome-only eval is insufficient

An outcome-only check (usually: does the final text answer look right, graded by a judge or matched to an expected string) is blind to three whole classes of production failure:

1. **Right destination, wrong or dangerous path.** The agent refunds the correct amount but does it by calling `delete_order` then `create_order` instead of `update_order`, silently losing the order's fulfillment history. The final text summary ("refund processed") is indistinguishable from the correct run.
2. **Lucky success that won't repeat.** The agent guesses a tool argument correctly this one time (temperature-driven variance) but the same prompt fails the argument extraction 3 times out of 4 on repeated attempts. A single outcome-pass tells you nothing about the reliability you'll see at scale.
3. **Self-reported success that's false.** The agent's final message says "I've updated your subscription," but the tool call actually returned an error the agent didn't notice or chose to paper over. Grading the summary text instead of the actual end state certifies a failure as a success.

### Trajectory evaluation

A trajectory is the ordered sequence of (thought, tool call, tool result) tuples for one run. Evaluating it means answering: is this a *reasonable* path to the goal, not necessarily an identical one to some reference?

Two approaches, usually combined:

- **Golden-trajectory matching.** You author or record a canonical correct trajectory for a task (the tool calls a competent human/agent would make, in a defensible order) and compare the actual run against it. Exact-match (same tools, same order, same arguments) is too strict — there are often multiple valid paths — so production systems use fuzzy matching: same *set* of required tool calls present (regardless of order, where order genuinely doesn't matter), no *forbidden* calls present (e.g. never calls `delete_account` for a "pause my subscription" task), and argument correctness checked per call.
- **LLM-judge-on-trace.** Feed the full trajectory (thoughts, calls, results) to a judge model and ask it to score dimensions like tool selection, argument extraction, result utilization, error recovery, plan coherence — six dimensions is a common decomposition, scored independently rather than as one aggregate "was this good" number, because aggregating hides which specific capability regressed. This inherits every LLM-as-judge bias from `T08-llm-as-judge` (verbosity, position when comparing two trajectories, self-preference if judge and agent share a model family) — calibrate it the same way.

Concretely, without memory/context engineering, one measured baseline trajectory-accuracy score was as low as 0.12 (12% of runs followed a correct reasoning path) on a multi-step benchmark; targeted fixes (better tool descriptions, explicit planning steps, memory of prior turns) have been reported to lift trajectory accuracy by 20-47 percentage points and goal completion by up to 32 points in comparable setups — the exact numbers are benchmark-specific, but the magnitude of the gap between "looks plausible" and "followed a correct path" is the point: it is large, and outcome-only eval would not have shown it to you at all.

### Tool-call accuracy and argument correctness

Score this per call, not per trajectory, and keep it binary and deterministic wherever possible:

```python
# untested sketch
def score_tool_call(actual_call: dict, expected_call: dict) -> dict:
    """actual_call/expected_call: {"name": str, "args": dict}"""
    tool_correct = actual_call["name"] == expected_call["name"]
    if not tool_correct:
        return {"tool_correct": False, "args_correct": False, "reason": "wrong tool"}

    arg_errors = []
    for key, expected_val in expected_call["args"].items():
        actual_val = actual_call["args"].get(key, "<missing>")
        if actual_val != expected_val:
            arg_errors.append(f"{key}: expected {expected_val!r}, got {actual_val!r}")

    return {
        "tool_correct": True,
        "args_correct": len(arg_errors) == 0,
        "arg_errors": arg_errors,
    }
```

For arguments with legitimate variation (free-text fields, IDs generated at runtime), use a verifier function instead of exact match — e.g. "does the `date` argument fall within the range implied by the user's request" rather than string equality. Reserve an LLM judge for tool-call correctness only when the argument space is genuinely open-ended (a natural-language `query` parameter to a search tool) — for everything else, deterministic checks are cheaper, faster, and don't inherit judge bias.

### Task completion rate

Define completion against **actual system state**, never the agent's self-report:

- Did the database row actually change to the expected value?
- Was the email actually sent (check the mail provider's send log, not the agent saying "email sent")?
- Did a downstream side effect that a human user would notice actually occur?

This usually means your eval harness needs a way to snapshot and query the state of a sandboxed environment (a test database, a mocked but stateful API) before and after the run, not just capture the agent's final text output. tau-bench's environments are built exactly this way — each domain (retail, airline) has a real underlying database the agent's tool calls mutate, and task success is checked against that database state plus the policy document the agent was supposed to follow, not against the conversation transcript.

### Cost and steps per task as first-class metrics

Track these on every eval run, not as an afterthought:

- **Steps per task** — a proxy for efficiency and for runaway-loop risk. A task that should take 3 tool calls and takes 15 is either solving a harder-than-expected case or stuck in a retry loop; both are worth flagging even if it eventually "succeeds."
- **Cost per task** ($, tokens) — directly ties to unit economics; an agent with 2 points higher accuracy but 4x the cost per task is not a strict win, it's a Pareto tradeoff you have to make explicitly.
- **Wall-clock per task** — user-facing latency; a "successful" agent that takes 90 seconds may fail on a product requirement even though it passes every accuracy metric.

Report these as distributions (p50/p95, not just mean) — a mean cost of $0.08/task can hide a p95 of $1.20/task from a small number of runs that spiral into long tool-call chains, and that tail is often where real incidents live.

### Golden trajectories and how to build them

1. **Start from real production traces**, not synthetic ones — have a human or a strong agent solve the task, capture the full trajectory, and have a domain expert lightly edit it into a canonical version (remove any accidental inefficiency, keep the essential tool calls and order where order matters).
2. **Mark what's required vs. incidental.** Explicitly annotate which tool calls are mandatory (must appear), which are forbidden (must never appear for this task), and which are optional/order-independent (fine either way). This is what makes fuzzy matching possible instead of forcing brittle exact-match.
3. **Cover the policy edge cases, not just the happy path.** A golden set built only from easy successful runs won't catch regressions in error recovery or policy compliance (e.g., an airline agent that should refuse to book past a fare rule cutoff).
4. **Version the golden set alongside the agent's tools/prompts.** When a tool's schema changes, the golden trajectories referencing its old argument names need updating too, or your eval starts failing for reasons that have nothing to do with agent quality.

### Handling nondeterminism: results as distributions

An agent's temperature, tool-latency-dependent branching, and even provider-side model updates all introduce run-to-run variance. Treat every eval number as a sample from a distribution, not a single ground truth:

- **pass^k**: run the same task k times, report the fraction where *all k* runs succeed. This is a much harder bar than pass@1 (any success in k tries) and is the more honest number for "can I rely on this in production," where a user hitting the failure case even once is a real incident. Reported gaps are large in practice — e.g. pass^1 around 70-80% dropping to pass^8 below 25% on realistic multi-turn retail tasks for capable models — meaning an agent that looks 80% reliable from a single run is often far less reliable under repeated real-world use.
- Run each eval task **N ≥ 3-5 times** minimum before drawing any conclusion about a regression; a single failed run after a prompt change is not evidence of a regression, it might just be sampling variance.
- Report **confidence intervals**, not point estimates, when comparing two agent versions — a 2-point accuracy difference on a 50-task eval set run once is well within noise.

### CI gates that don't flake

- **Never gate on a single run.** Run each eval task multiple times and gate on an aggregate statistic (mean pass rate over N runs, or pass^k for a k appropriate to your risk tolerance) with a pre-registered threshold, not "did it pass this time."
- **Separate deterministic checks from judge-based checks in the gate logic.** Tool-call argument correctness and task-completion-against-state should be exact/deterministic and can gate hard (any regression blocks merge). LLM-judge trajectory scores should gate on a statistically significant drop across a run-set, not a single trace, because the judge itself has variance.
- **Pin the judge model version and the agent's model version independently** in the CI config, so a provider-side silent model update doesn't retroactively make yesterday's green build look different today with no code change.
- **Quarantine known-flaky tasks** rather than letting one genuinely hard task with irreducible variance block every PR — track its pass rate over time as a metric, but don't let it gate merges until either the task or the agent's reliability on it improves.
- **Fix the environment's own nondeterminism** (mock external API latency/failures deterministically in the eval sandbox, seed any randomness in tool implementations) — much of what looks like "agent flakiness" is actually eval-harness flakiness from an under-controlled environment.

---

## Build it from scratch

Minimal agent eval harness scoring tool-call accuracy, task completion against state, and pass^k — the shape of what an interviewer may ask you to sketch.

```python
# untested sketch
from dataclasses import dataclass, field
from collections import Counter

@dataclass
class TrajectoryResult:
    tool_calls: list[dict]           # [{"name": ..., "args": {...}}, ...]
    final_state: dict                # snapshot of sandbox DB/state after run
    cost_usd: float
    n_steps: int

@dataclass
class Task:
    task_id: str
    required_calls: list[dict]       # must all appear (order-independent unless flagged)
    forbidden_calls: list[str]        # tool names that must never appear
    expected_state: dict              # subset of state that must match after run
    ordered: bool = False             # if True, required_calls order must match

def score_run(task: Task, result: TrajectoryResult) -> dict:
    called_names = [c["name"] for c in result.tool_calls]

    forbidden_hit = any(name in called_names for name in task.forbidden_calls)

    required_present = all(
        any(c["name"] == req["name"] and c["args"] == req["args"]
            for c in result.tool_calls)
        for req in task.required_calls
    )

    state_correct = all(
        result.final_state.get(k) == v for k, v in task.expected_state.items()
    )

    return {
        "task_id": task.task_id,
        "tool_call_accuracy": required_present and not forbidden_hit,
        "task_completed": state_correct,          # checked against STATE, not agent text
        "cost_usd": result.cost_usd,
        "n_steps": result.n_steps,
    }

def pass_k(results_across_k_runs: list[dict]) -> float:
    """All k runs of the SAME task must succeed for it to count."""
    return float(all(r["tool_call_accuracy"] and r["task_completed"]
                      for r in results_across_k_runs))

def eval_suite(tasks: list[Task], run_agent_fn, k: int = 4) -> dict:
    per_task_pass_k = {}
    costs = []
    for task in tasks:
        runs = [score_run(task, run_agent_fn(task)) for _ in range(k)]
        per_task_pass_k[task.task_id] = pass_k(runs)
        costs.extend(r["cost_usd"] for r in runs)

    return {
        "pass_k": sum(per_task_pass_k.values()) / len(tasks),
        "per_task": per_task_pass_k,
        "p50_cost": sorted(costs)[len(costs)//2],
        "p95_cost": sorted(costs)[int(len(costs)*0.95)],
    }
```

Full version with fuzzy trajectory matching, an LLM-judge trajectory scorer with the six-dimension decomposition, and a CI gate that quarantines flaky tasks: **`(lab pending)`**.

---

## How it's done in production

**LangSmith** — built by the LangChain/LangGraph team, gives node-by-node state diffs on the full agent graph, agent sandboxing for safe replay, and "replay against a new model" to isolate regressions from a model swap versus a prompt/tool change. Best fit when the agent is already built on LangGraph. **Braintrust** — connects dataset management, scoring, production monitoring, and CI release gates in one system; strong for eval-driven development workflows where you want the eval suite versioned alongside prompts. **Arize Phoenix** — OpenTelemetry-native trace capture, trajectory-level span analysis, and production drift detection; open-source and a strong free option when you want vendor-neutral tracing. **tau-bench / tau2-bench** — not a production tool but the reference benchmark shape to imitate: realistic multi-turn tool-and-simulated-user tasks against a real mutable backend, with the pass^k metric built in; worth building your internal eval harness in this shape rather than inventing your own from scratch.

**Failure-mode table:**

| Symptom | Cause | Fix |
|---|---|---|
| Eval suite shows 90%+ pass rate, production complaint rate is high | Outcome-only grading (judge reads agent's final summary text, not actual state) | Check task completion against real system state, not the agent's self-report |
| Same task passes on Monday's CI run and fails on Tuesday's with no code change | Nondeterminism treated as a bug instead of expected variance; gating on a single run | Run N≥3-5 repeats, gate on aggregate/pass^k with a pre-registered threshold |
| Trajectory looks totally different between two "passing" runs of the same task | No fuzzy golden-trajectory matching — either too strict (never matches) or absent entirely | Author goldens with required/forbidden/optional call annotations, not brittle exact-match |
| Agent's accuracy improved after a model upgrade, but CI gate didn't catch a cost blowup | Cost/steps not tracked as first-class metrics alongside accuracy | Track p50/p95 cost and steps per task on every run; gate on Pareto tradeoff, not accuracy alone |
| CI gate is disabled/ignored by the team within a month of shipping it | Gate flakes constantly because it was built on single-run pass/fail | Separate deterministic checks (hard gate) from LLM-judge checks (statistical gate over a run-set); quarantine known-hard tasks |
| Agent regresses only on error-recovery cases, invisible in the eval dashboard | Golden set built entirely from happy-path traces | Build goldens explicitly covering policy edge cases and induced-failure recovery, not just successful runs |
| Judge-scored trajectory quality keeps rising while tool-call accuracy (deterministic) quietly falls | Judge bias inflating trajectory scores independent of real tool correctness (see `T08-llm-as-judge`) | Never let a judge-based aggregate mask a deterministic per-call regression; report both, gate on the deterministic one |

---

## Tradeoffs & when NOT to use it

- **Don't build a full six-dimension LLM-judge trajectory scorer for a single-tool, single-step agent.** If there's no meaningful path to evaluate (one tool call, deterministic outcome), a plain tool-call-accuracy + task-completion check is the whole eval; trajectory scoring is overhead with nothing to measure.
- **Don't rely on pass@1 for anything you plan to ship at real user volume.** A single successful run is close to meaningless evidence of production reliability given documented pass^k drop-offs; always report the harder multi-repeat number for anything gating a launch decision.
- **Don't use an LLM judge to check tool-call argument correctness when a deterministic verifier is possible.** It's slower, costs more, and inherits judge bias for a check that should be exact-match or a simple validator function.
- **Golden trajectories go stale.** If tool schemas or the underlying policy change frequently, the maintenance cost of keeping goldens in sync can exceed their value; in a fast-changing agent, weight relatively more on task-completion-against-state checks (which are more robust to internal path changes) and less on strict trajectory matching.
- **Cost/step tracking is overkill for a prototype or an internal tool with no real usage volume** — instrument it before scaling, not before you've validated the agent is worth scaling at all.
- **Don't treat a benchmark like tau-bench as a proxy for your specific domain's reliability.** It's the right shape to imitate, not a stand-in for evaluating your actual tools, actual policies, and actual failure modes — build your own domain-specific tasks and goldens using the same methodology.

---

## Interview questions

### Q1 — Why is outcome-only evaluation insufficient for agents?
**Testing:** baseline understanding of the core problem this module addresses.
**Answer:** An agent can reach a plausible-looking final answer via a wrong or dangerous path (right amount refunded through the wrong tool, losing state elsewhere), via a lucky one-off success that won't repeat under real variance, or by self-reporting success when the actual tool call failed. Outcome-only grading — reading the final text — can't distinguish any of these from a genuinely correct run.
**Follow-up trap:** *"Give me a concrete example where outcome-only eval passes but the run is actually broken."* — an agent asked to "pause my subscription" that calls `cancel_subscription` instead of `pause_subscription`, then summarizes "your subscription has been paused" — the final text is correct-sounding and wrong; only a tool-call-accuracy or state check catches it.

### Q2 — What is trajectory evaluation and how do you actually implement it?
**Answer:** Scoring the full sequence of (thought, tool call, result) steps against either a golden trajectory (fuzzy-matched: required calls present, forbidden calls absent, order enforced only where it genuinely matters) or an LLM judge reading the whole trace and scoring dimensions like tool selection, argument extraction, error recovery, and plan coherence independently rather than as one aggregate score.
**Follow-up trap:** *"Why score six dimensions independently instead of one aggregate trajectory quality number?"* — an aggregate hides which specific capability regressed; if tool selection stays perfect but error recovery degrades after a change, an aggregate score might not move enough to trip an alert, while the per-dimension score for error recovery would.

### Q3 — Define tool-call accuracy precisely. What's the difference between checking it with a deterministic verifier vs. an LLM judge?
**Answer:** Tool-call accuracy is binary per call: did the agent call the correct tool, with arguments matching expected values (or satisfying a verifier function for open-ended fields). Deterministic verification (exact match, regex, range check) is preferred wherever the argument space allows it — cheaper, faster, zero judge bias. An LLM judge is reserved for genuinely open-ended arguments (free-text search queries) where no deterministic check captures "close enough."
**Follow-up trap:** *"The argument is a free-text natural-language query to a search tool — how do you check that deterministically?"* — you generally can't fully; use a verifier that checks the query contains the required entities/constraints from the user's request (a partial deterministic check) and reserve judge-based semantic-closeness scoring only for the residual open-endedness, rather than judging the whole argument from scratch.

### Q4 — How do you measure task completion, and why is checking the agent's final message the wrong approach?
**Answer:** Task completion must be checked against actual system state — did the database row change, was the email actually sent per the provider's log, did the expected side effect occur — never against the agent's self-reported summary text, because an agent can produce a confident, well-formed success message describing an action that didn't actually happen or happened wrong.
**Follow-up trap:** *"Your sandbox environment doesn't have real side effects to check — it's all mocked. Now what?"* — make the mock stateful and inspectable (a real in-memory or test database the tool calls actually mutate, per tau-bench's design), so "state after the run" is a real queryable artifact rather than trusting either the agent or a mock's return value at face value.

### Q5 — What is pass^k and why does it matter more than pass@1 for production decisions?
**Testing:** whether the candidate has internalized nondeterminism as a first-class concern.
**Answer:** pass^k runs the same task k times and only counts it as a pass if ALL k runs succeed — a much harder bar than pass@1 (success in at least one of k tries). Reported gaps are large: pass^1 around 70-80% can drop to pass^8 below 25% on realistic multi-turn tasks even for capable models. Pass@1 tells you the agent *can* succeed; pass^k tells you how often a real user hitting this task repeatedly will actually get a consistent good outcome, which is the number that matters for reliability commitments.
**Follow-up trap:** *"Your pass^8 is 25% but pass@1 is 78%. Is the agent broken?"* — not necessarily broken, but unreliable enough that you shouldn't promise consistent behavior at that task; investigate whether the variance comes from a specific sub-step (e.g. one flaky tool-argument-extraction case) rather than uniform noise across the whole trajectory — targeted fixes to the highest-variance step often move pass^k much more than generic prompt tuning.

### Q6 — How do you build a golden trajectory, and what's the biggest mistake teams make building them?
**Answer:** Record a real production or expert-solved run, lightly edit it into a canonical version with a domain expert, and explicitly annotate which calls are required, which are forbidden, and which are order-independent/optional — this is what makes fuzzy matching possible. The biggest mistake is building the golden set entirely from easy happy-path traces, which means the eval never exercises error recovery or policy-edge-case behavior and a regression there goes completely undetected.
**Follow-up trap:** *"Your tool's argument schema just changed — every golden trajectory referencing it now fails. Is that a real regression?"* — no, that's golden-set staleness, not an agent regression; version your goldens alongside your tool schemas and treat a mass failure immediately after a schema change as a signal to update the goldens, not the agent.

### Q7 — Why must cost and steps-per-task be first-class metrics rather than an afterthought?
**Answer:** An agent that gains 2 points of accuracy by taking 4x the tool calls and 4x the token cost per task is not a strict improvement — it's a Pareto tradeoff that needs an explicit decision, and if cost/steps aren't tracked as metrics on every eval run, that tradeoff gets made silently and shows up later as a unit-economics surprise. Steps-per-task is also a leading indicator of runaway-loop risk before it becomes a full-blown incident.
**Follow-up trap:** *"Report cost as a single mean number across your eval suite — what does that hide?"* — the tail: a mean of $0.08/task can hide a p95 of $1.20/task from a small number of runs that spiral into long retry/tool-call chains, and that tail is usually where the real production incidents and budget blowouts live, not the median.

### Q8 — Design a CI gate for an agent's eval suite that won't get disabled by the team within a month.
**Testing:** the practical engineering-culture question underneath the metrics.
**Answer:** Never gate on a single run — run each task N≥3-5 times and gate on an aggregate statistic (mean pass rate or pass^k) with a pre-registered threshold. Separate deterministic checks (tool-call accuracy, task-completion-against-state — these can hard-gate on any regression) from LLM-judge-based checks (which should gate on a statistically significant drop across a run-set, since the judge itself has variance). Pin both the agent's and the judge's model versions explicitly in CI config. Quarantine known-flaky tasks and track their pass rate as a metric without letting them block merges.
**Follow-up trap:** *"Your team disabled the gate last quarter because it kept blocking unrelated PRs. What likely went wrong?"* — almost certainly gating on single-run pass/fail with no statistical aggregation, or not separating deterministic from judge-based checks, so ordinary judge variance or a genuinely hard-but-known-flaky task was treated as a hard blocker on every PR regardless of relevance.

### Q9 — An agent's tool-call accuracy is perfect but users still report bad experiences. Where do you look?
**Answer:** Tool-call accuracy alone doesn't capture trajectory quality (a technically-correct-but-wasteful path, poor error recovery when a tool legitimately fails, unnecessarily many steps causing latency) or the actual end-state correctness beyond the specific calls you're checking. Look at the full trajectory score (the six-dimension judge breakdown), task completion against real state (not just "the tools that were called were the right ones" — check whether the *sequence and outcome* actually solved the user's goal), and latency/step-count distributions.
**Follow-up trap:** *"You find error recovery is the weak dimension specifically. What's your fix, and how do you verify it worked?"* — add explicit induced-failure test cases to the golden/eval set (simulate a tool timeout or an error response mid-trajectory) so error recovery is actually exercised rather than incidentally covered, then re-measure pass^k specifically on that subset before and after the fix — a generic overall-accuracy number won't isolate whether the targeted fix worked.

### Q10 — How would you evaluate a multi-agent system where a supervisor delegates to sub-agents?
**Testing:** whether the candidate can extend single-agent eval concepts to composition.
**Answer:** Evaluate each sub-agent's trajectory and tool-call accuracy independently (so a regression is attributable to the specific sub-agent, not just "the system got worse somewhere"), plus the supervisor's routing/delegation decisions as their own trajectory-scored layer (did it delegate to the right sub-agent, did it correctly integrate sub-agent results without losing or corrupting information at the handoff). Task completion is still checked against final system state, but you additionally want handoff-fidelity checks — does the sub-agent's output survive being summarized back to the supervisor without silently dropping caveats or uncertainty the sub-agent flagged.
**Follow-up trap:** *"The supervisor's summary of a sub-agent's uncertain result reads as confident. How do you catch that in eval, since the final task might still 'complete' correctly?"* — this needs a dedicated check comparing the sub-agent's raw output (including any hedging/uncertainty markers) against what the supervisor reports upstream — a form of trajectory eval focused specifically on information-fidelity at agent-to-agent handoffs, which a pure task-completion-against-state check won't catch since the underlying action might still have gone through correctly.

### Q11 — What's the risk of using an LLM judge to score agent trajectories, and how does it interact with the biases from `T08-llm-as-judge`?
**Answer:** Every documented LLM-judge bias applies directly: verbosity bias can inflate scores for trajectories with more reasoning text even if the actual path wasn't better; self-preference bias is a real risk if the judge and the agent share a model family; position bias matters when comparing two trajectories pairwise. On top of that, trajectory traces are long, so the judge's own context-handling limitations (attention degrading over long inputs) add a failure mode specific to this use case that a short single-turn judge call doesn't have.
**Follow-up trap:** *"How do you calibrate a trajectory judge specifically, given traces are too long for a human to quickly re-read?"* — same methodology as any judge calibration (`T08-llm-as-judge`), but budget more human time per trace since trajectories take longer to review; consider decomposing calibration per-dimension (have humans just judge "was error recovery good" on a shorter excerpt) rather than asking humans to holistically re-judge the entire multi-thousand-token trace at once.

### Q12 — You need to gate a release on agent eval results, but the eval suite takes 6 hours to run with N=5 repeats per task. How do you make this practical?
**Testing:** engineering pragmatism under real constraints.
**Answer:** Tier the suite: a fast, small, high-signal subset (the highest-risk/highest-frequency task types, run at full N-repeat rigor) gates every PR in minutes; the full suite with full repeats runs on a slower cadence (nightly, or pre-release) and gates the actual release, not every commit. Parallelize task execution across workers since tasks are independent. Cache/mock expensive external dependencies in the fast tier so latency is bounded by the agent's own reasoning time, not real API latency.
**Follow-up trap:** *"The fast subset passes but the full nightly suite catches a regression a day later. Is the tiered gate a failure?"* — no, that's the tiered gate working as designed — it traded some detection latency for PR-time speed deliberately; the actual failure would be if the full suite result doesn't feed back into blocking the release before it ships, or if the fast subset was chosen without actually correlating with the full suite's failure modes (which should be validated periodically, not assumed).

---

## Red flags that fail you

- Grading agent success by reading the agent's own final summary text instead of checking actual system state.
- Citing a pass@1 number as if it represents production reliability, with no mention of repeat-run variance.
- Treating a single failed CI run as proof of a regression without checking if it's within normal variance.
- Building or trusting a golden-trajectory set made entirely of happy-path traces.
- Using an LLM judge for a tool-call argument check that a simple deterministic verifier could handle.
- Reporting accuracy with no cost or step-count numbers alongside it.
- Not knowing what pass^k means when asked directly.

---

## Cheat card

```
WHY OUTCOME-ONLY FAILS   right destination/wrong path · lucky one-off success ·
                         agent self-reports success that didn't actually happen

LAYERS                   1. tool-call accuracy    (binary, per call, deterministic
                            where possible; verifier fn for open-ended args)
                         2. trajectory eval        (golden fuzzy-match: required/
                            forbidden/optional calls; OR llm-judge, 6 dims scored
                            independently: tool selection, arg extraction, result
                            use, error recovery, plan coherence, task completion)
                         3. task completion        vs ACTUAL STATE, never agent's
                            own summary text
                         4. cost/steps per task     $ + tokens + steps, p50 AND p95,
                            first-class metric alongside accuracy every run

GOLDEN TRAJECTORIES      build from real/expert runs, human-edited to canonical ·
                         annotate required / forbidden / order-independent calls ·
                         cover POLICY EDGE CASES + induced-failure recovery, not
                         just happy path · version alongside tool schemas

NONDETERMINISM           pass@1 = success in >=1 of k tries (optimistic)
                         pass^k = ALL k tries succeed (honest reliability number)
                         reported gap: pass^1 ~70-80% -> pass^8 <25% (tau-bench,
                         realistic multi-turn retail tasks)
                         run N>=3-5 repeats before calling ANYTHING a regression

CI GATES                 hard-gate deterministic checks (tool-call acc, state)
                         statistical-gate judge-based checks (drop across a run-
                         set, not one trace) · pin agent AND judge model versions
                         · quarantine known-flaky tasks, don't let them block

BENCHMARK SHAPE          tau-bench / tau2-bench: real mutable backend + policy
                         doc + simulated user, pass^k built in — imitate this
                         shape for your own domain, don't just cite the score

TOOLS                    LangSmith (LangGraph-native, node diffs, replay) ·
                         Braintrust (dataset+score+monitor+CI in one) ·
                         Arize Phoenix (OTel-native tracing, drift detection)
```

## Sources

- [τ-bench: A Benchmark for Tool-Agent-User Interaction in Real-World Domains (arXiv:2406.12045)](https://arxiv.org/pdf/2406.12045) — accessed 2026-07-26
- [τ2-Bench: Evaluating Conversational Agents in a Dual-Control Environment (arXiv:2506.07982)](https://arxiv.org/pdf/2506.07982) — accessed 2026-07-26
- [LLM Agent Evaluation Metrics in 2026: Tool Calling, Task Completion, Reasoning, and Trace-Based Evals — Confident AI](https://www.confident-ai.com/blog/llm-agent-evaluation-complete-guide) — accessed 2026-07-26
- [The Definitive Guide to AI Agent Evaluation (2026) — FutureAGI](https://futureagi.com/blog/definitive-guide-ai-agent-evaluation-2026/) — accessed 2026-07-26
- [AI Agent Evaluation (2026): Metrics, Frameworks, and Production Failures — Morph](https://www.morphllm.com/ai-agent-evaluation) — accessed 2026-07-26
- [AI Agent Trajectory Testing 2026: LangSmith vs Braintrust vs Arize Phoenix vs Galileo — genai.qa](https://genai.qa/ai-agent-trajectory-testing-2026/) — accessed 2026-07-26
- [How to Build an Agent Evaluation Framework With Metrics, Rubrics, and Benchmarks — Galileo](https://galileo.ai/blog/agent-evaluation-framework-metrics-rubrics-benchmarks) — accessed 2026-07-26

## Changelog
- 2026-07-26 — created
