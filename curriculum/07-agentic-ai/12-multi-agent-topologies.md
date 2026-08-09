# Multi-Agent Topologies (and When NOT To)

> **Track:** T07 Agentic AI · **Time:** 2.5h · **Prereqs:** `T07-agent-loop-from-scratch`, `T07-context-engineering` · **Updated:** 2026-07-26
> **Module id:** `T07-multi-agent-topologies` · **Tags:** sprint (W4), architecture
> **Lab:** none yet — see `labs/py/02-agent-loop/` for the pattern if you want to build one

## The 30-second version

There are five topologies worth knowing and they differ on exactly two axes: **who decides what happens next** and **what context crosses the boundary**. **Supervisor** centralises routing, so every decision is visible in one trace. **Hierarchical** nests supervisors when the team count exceeds what one router can select over. **Swarm/handoff** lets peers transfer control directly, which is faster and much harder to reason about. **Blackboard** removes messaging entirely in favour of a shared state object that agents read and write. **Debate** runs independent attempts and has them critique each other, and the evidence for it is genuinely mixed. Then the part that actually gets you hired: **a single agent with good tools beats a poorly decomposed multi-agent system almost always**, because decomposition adds routing errors, lossy context handoffs, multiplied latency, multiplied cost, and a debugging surface where the failure is in the *seam* rather than in any agent. The Berkeley MAST work annotated 1,600+ traces across 7 frameworks and found the dominant failure categories are system design and inter-agent misalignment, not model capability. Split only when you have a specific reason: parallel read-heavy subtasks with small outputs, mandatory context isolation, a genuine permission or trust boundary, or independent deployment ownership. "We have twenty tools" and "the org chart has four teams" are not reasons.

## Why this gets asked

Because it is the single most common senior interview trap in agentic AI. The question is phrased as "design a multi-agent system for X" and the thing being tested is whether you will *accept the premise*. Candidates who immediately draw a researcher, a writer, and a critic have failed the question before they finish the diagram. The interviewer has personally shipped a multi-agent system, watched it cost 10x and perform worse, spent two weeks tracing a failure that turned out to be a supervisor mis-routing 8% of requests, and torn it down to one agent with better tools. They want to hear the costs named unprompted, and they want to hear the specific conditions under which you *would* split, because refusing all decomposition is also wrong — Anthropic's own Research feature is orchestrator-plus-subagents and reported beating single-agent Opus 4 by 90.2% on research tasks. The signal is discrimination, not doctrine.

---

## Lineage: past → present → future

**What came before.** Multi-agent systems long predate LLMs. The 1980s-90s produced blackboard architectures (HEARSAY-II for speech understanding, where independent knowledge sources posted hypotheses to shared state), the Contract Net protocol (Smith, 1980) for task allocation by bidding, BDI architectures, and FIPA-ACL as a standardised agent communication language. All of it worked in closed domains and all of it died on the same rock: **the coordination logic had to be written by hand, and writing it was harder than writing the task**. The LLM era restarted the cycle from scratch and made the same mistakes faster. AutoGen (Microsoft Research, 2023) popularised conversational multi-agent with `GroupChat`; CrewAI made role-play crews ("you are a senior researcher") a one-liner; and both produced spectacular demos and a well-documented set of production failures — agents politely agreeing with each other into a wrong answer, group chats that never terminated, and role prompts doing no measurable work. OpenAI's **Swarm** (Oct 2024) was an explicitly experimental library that named the handoff pattern cleanly and was later superseded by the OpenAI Agents SDK. The pain that killed naive conversational multi-agent was cost and non-determinism: you could not predict how many LLM calls a `GroupChat` would make, could not reproduce a failure, and could not point at where the error entered.

**Where it stands now.** The frameworks consolidated: Microsoft merged AutoGen and Semantic Kernel into the **Microsoft Agent Framework**, public preview Oct 2025, 1.0 for Python and .NET on 3 Apr 2026. LangGraph ships both `langgraph-supervisor` and `langgraph-swarm`, with handoffs implemented as `Command(goto=..., graph=Command.PARENT)`. The OpenAI Agents SDK offers two distinct mechanisms whose difference matters in interviews: **handoffs** transfer control and the receiving agent sees the entire prior conversation, whereas **agents-as-tools** keeps the caller in control and returns only a result. Google's A2A protocol went to the Linux Foundation and hit 1.0 in April 2026 with 150+ organisations, signed Agent Cards, and SDKs in five languages — which matters because it makes *cross-organisation* agent interop a real thing rather than a slide. And the empirical picture got much better and much less flattering. **MAST** (Cemri et al., arXiv:2503.13657, v3 Oct 2025) opens with the finding that "performance gains on popular benchmarks are often minimal", annotates 1,600+ traces across 7 frameworks, and derives 14 failure modes in 3 categories: system design issues, inter-agent misalignment, and task verification. The headline is that failures come from *design*, not from model weakness. On the other side, Anthropic's multi-agent Research system reported a 90.2% improvement over single-agent Opus 4 on research tasks at roughly 15x the token usage, with token usage alone explaining about 80% of performance variance on browsing evals. **The live disagreement is sharp and worth naming both sides.** Cognition's "Don't Build Multi-Agents" (June 2025) argues for single-threaded linear agents with a dedicated compression model, because subagents have no context of each other's work and the handoff is where quality dies. Anthropic argues for parallel isolated subagents on breadth-first research. Both are correct about the task shapes they built for, and the synthesis that has emerged in practice is: **orchestrator plus ephemeral read-only subagents, writes single-threaded.** Multi-agent debate is the one area where the evidence went the *other* way in 2025-2026: controlled studies find homogeneous unguided debate imposes a 2.1x-3.4x token multiplier for accuracy that is statistically comparable to or worse than isolated self-correction, with three named failure modes — sycophantic conformity, contextual fragility, and consensus collapse.

**Where it's heading.** High confidence: **the orchestrator-plus-subagents shape wins and everything else recedes**, because it is the only topology whose cost and control flow you can predict. High confidence: **the interesting boundary becomes organisational, not architectural** — A2A exists so *your* agent can call *another company's* agent, and that is a genuine reason for multiple agents that has nothing to do with decomposing your own task. Medium confidence: **routing becomes a trained component rather than a prompt**, with small classifiers or fine-tuned routers replacing "ask the big model which team should handle this", because routing errors are a top failure mode and a classifier is cheaper, faster, and measurable. Speculative: emergent multi-agent societies, agent marketplaces, and negotiation protocols. Treat confident claims about swarms as fashion until someone shows you an eval, and note that the field's own best data (MAST) says the gains have so far been minimal.

---

## Mental model

Two axes generate all five topologies.

```
                    WHO DECIDES WHAT HAPPENS NEXT?
                central (one router)          distributed (peers)
              ┌────────────────────────────┬────────────────────────────┐
  FULL        │  SUPERVISOR                │  SWARM / HANDOFF           │
  (whole      │  routes, sees everything   │  peer transfers control    │
  history     │  one trace, one bottleneck │  fast, hard to trace       │
  crosses)    │  OpenAI: agents-as-tools   │  OpenAI: handoffs          │
              ├────────────────────────────┼────────────────────────────┤
  DISTILLED   │  ORCHESTRATOR + SUBAGENTS  │  BLACKBOARD                │
  (summary    │  fresh window per worker   │  no messages; shared state  │
  crosses)    │  50k spent → 1-2k returned │  agents read/write a store │
              │  ← THE ONE THAT USUALLY    │  contention + write order   │
              │     WINS                    │  are the hard parts        │
              └────────────────────────────┴────────────────────────────┘

  HIERARCHICAL = supervisor whose workers are supervisors (recursion on axis 1)
  DEBATE       = N independent attempts + critique rounds (orthogonal: it is a
                 quality mechanism, not a decomposition; evidence is mixed)
```

The thing to internalise: **the topology is a decision about the seams, and the seams are where the failures live.** Each boundary you draw is a place where context is lost, a routing decision can be wrong, latency is added, and a trace becomes discontinuous. You are not adding agents, you are adding *interfaces*, and you should price them the way you price a network hop between microservices — because that is exactly what they are, except the payload is natural language and the contract is unenforced.

---

## How it actually works: the five topologies

### 1. Supervisor (orchestrator-worker)

One agent owns routing. Workers do not talk to each other. Every decision passes through one place, which is the entire point.

```
                 ┌─────────────┐
   user ────────▶│ SUPERVISOR  │◀──────── all results return here
                 │  routes,    │
                 │  synthesises│
                 └──┬───┬───┬──┘
          ┌─────────┘   │   └─────────┐
          ▼             ▼             ▼
    ┌──────────┐  ┌──────────┐  ┌──────────┐
    │ SQL agent│  │ Doc agent│  │ Web agent│     workers never talk to each other
    │ (read)   │  │ (read)   │  │ (read)   │
    └──────────┘  └──────────┘  └──────────┘
```

```python
# LangGraph-shaped supervisor. The routing decision is STRUCTURED, not free text.
from typing import Literal, TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.types import Command
from pydantic import BaseModel

class Route(BaseModel):
    """Structured routing output. Never parse a route out of prose."""
    next: Literal["sql", "docs", "web", "FINISH"]
    subtask: str          # the self-contained instruction for the worker
    why: str              # forces the model to justify; also your debug field

class State(TypedDict):
    messages: list
    findings: list[dict]  # worker → {agent, answer, evidence, confidence}
    hops: int

MAX_HOPS = 6              # routing budget: without this you have an infinite router

def supervisor(state: State) -> Command:
    if state["hops"] >= MAX_HOPS:
        return Command(goto="synthesise")
    route = llm.with_structured_output(Route).invoke([
        {"role": "system", "content": SUPERVISOR_PROMPT},   # names each worker + when to use it
        {"role": "user", "content": _brief(state)},         # task + findings so far, NOT raw history
    ])
    log.info("route", extra={"next": route.next, "why": route.why, "hop": state["hops"]})
    if route.next == "FINISH":
        return Command(goto="synthesise")
    return Command(goto=route.next,
                   update={"hops": state["hops"] + 1,
                           "current_subtask": route.subtask})

def make_worker(name: str, tools: list):
    def worker(state: State) -> Command:
        # FRESH context. The worker sees the subtask, not the conversation.
        result = run_agent(system=WORKER_PROMPTS[name], tools=tools,
                           task=state["current_subtask"], max_steps=8,
                           return_contract=WORKER_RETURN_CONTRACT)
        return Command(goto="supervisor",
                       update={"findings": [{"agent": name, **result}]})
    return worker
```

**Use it when** you can enumerate the worker roles up front, the subtasks are independent, and you need every decision in one trace. **The bottleneck is real**: every hop costs a supervisor LLM call, so a 4-worker task is 9 model calls (4 routes + 4 workers + 1 synthesis) at minimum. **The failure mode is misrouting**, and it is quiet — you get a plausible answer from the wrong specialist. Instrument route distribution and route-change rate; a supervisor that routes 30% of traffic to a worker that returns "not my area" is a measurable bug.

### 2. Hierarchical (supervisor of supervisors)

The same pattern, recursed, because a single router selecting over 15 workers degrades the same way a single agent selecting over 40 tools degrades.

```
                        ┌──────────────┐
                        │ TOP SUPERVISOR│
                        └───┬───────┬───┘
              ┌─────────────┘       └─────────────┐
      ┌───────▼────────┐                  ┌───────▼────────┐
      │ RESEARCH SUPER │                  │ ACTION SUPER   │   ← different permission tiers
      └──┬──────┬──────┘                  └──┬──────┬──────┘
         ▼      ▼                            ▼      ▼
      web    docs                        ticketing  email        (write tools live ONLY here,
                                                                  behind approval gates)
```

The only *good* reason to nest is that the sub-teams differ on something structural: permission tier, model tier, latency budget, or deployment ownership. Nesting purely to reduce a router's fan-out is a smell — the usual right answer is fewer, better-described workers. The specific cost of nesting is **latency stacking**: each level adds a routing call, so three levels means three sequential model calls before any work starts. At ~1.5s per routing call that is 4.5s of pure overhead before the first useful token.

### 3. Swarm / handoff (peer-to-peer)

No central router. Each agent has handoff tools and transfers control directly.

```
   user ──▶ [triage] ──handoff──▶ [billing] ──handoff──▶ [refunds]
                 ▲                                          │
                 └──────────── handoff back ────────────────┘
   control is wherever it was last handed. no single place to look.
```

```python
# LangGraph swarm-style handoff. The mechanism is Command(goto=..., graph=PARENT).
from langgraph.types import Command

def make_handoff_tool(target: str, description: str):
    @tool(name=f"transfer_to_{target}", description=description)
    def handoff(reason: str, context_summary: str) -> Command:
        """Transfer control. `context_summary` is the ONLY thing that reliably
        crosses if you are isolating context; make the model write it explicitly."""
        return Command(
            goto=target,
            graph=Command.PARENT,          # jump to a node in the parent graph
            update={"active_agent": target,
                    "handoff_note": {"from": _me(), "to": target,
                                     "reason": reason, "summary": context_summary}},
        )
    return handoff
```

**The tradeoff, stated the way an interviewer wants to hear it:** the swarm is *faster and cheaper* — no intermediary, direct transfers, fewer LLM calls — and the supervisor is *easier to reason about* — one routing node, explicit control flow, every decision visible in the trace. Choose the swarm when latency matters more than observability and the handoff graph is small and mostly linear (a triage funnel). Choose the supervisor when you will have to debug this at 3am.

**The specific trap** is what crosses on a handoff, and it is framework-dependent. In the OpenAI Agents SDK, a handoff transfers the *entire* message history — the receiving agent sees the whole conversation as if it had been there from the start. That is convenient and it means you get none of the context-isolation benefit; it also means input guardrails only apply to the first agent in the chain and output guardrails only to the agent that produces the final output, which is a real security gap people miss. In LangGraph you control the update payload, so isolation is possible but the summary is now a lossy artefact you must engineer.

### 4. Blackboard (shared state, no messaging)

Agents do not address each other at all. They read from and write to a shared structured store, and a controller decides who runs next based on the state.

```
        ┌──────────────────────── BLACKBOARD (typed, versioned) ───────────────┐
        │  goal: ...                                                            │
        │  hypotheses: [{id, claim, support[], status, author, version}]         │
        │  facts:      [{id, value, source, confidence}]                         │
        │  open_questions: [...]                                                │
        │  decisions:  [{id, choice, rationale, by, at}]                         │
        └──▲────────────▲─────────────▲──────────────▲───────────────────────────┘
           │ read/write │             │              │
      ┌────┴───┐   ┌────┴────┐   ┌────┴────┐   ┌────┴─────┐
      │gatherer│   │verifier │   │critic   │   │writer    │
      └────────┘   └─────────┘   └─────────┘   └──────────┘
                          ▲
                 CONTROLLER: picks the next agent whose precondition is satisfied
```

```python
# The part that makes blackboard work in practice: typed slots + optimistic
# concurrency. Free-text shared scratchpads become mud within ten writes.
@dataclass
class Hypothesis:
    id: str; claim: str; support: list[str]
    status: Literal["proposed", "supported", "refuted"]
    author: str; version: int

class Blackboard:
    def write(self, slot: str, item, *, expected_version: int, author: str):
        cur = self._store[slot].get(item.id)
        if cur and cur.version != expected_version:
            raise Conflict(f"{item.id} changed under {author}: "
                           f"expected v{expected_version}, found v{cur.version}")
        item.version = expected_version + 1
        self._store[slot][item.id] = item
        self._journal.append((time.time(), author, slot, item.id, item.version))

    def ready_agents(self) -> list[str]:
        """Precondition-driven scheduling; this replaces routing."""
        out = []
        if self._unverified_hypotheses(): out.append("verifier")
        if self._open_questions():        out.append("gatherer")
        if self._supported_and_unwritten(): out.append("writer")
        return out
```

**Use it when** the work is genuinely incremental and non-linear: multiple agents contributing evidence toward hypotheses, where the order is data-dependent rather than plannable. It is the best fit for research and analysis pipelines, and the journal gives you a genuinely good audit trail. **Do not use it as a shared scratchpad** — an untyped shared text blob is the worst of all worlds, because every agent rewrites everyone else's work and there is no way to attribute a change. Typed slots, versions, and a write journal, or don't do it. **The named failure is lost-update / write contention**: two agents update the same hypothesis, one silently wins, and the trace shows both succeeding. Optimistic concurrency with an explicit `Conflict` is what makes it visible.

### 5. Debate (and why to be sceptical)

N agents answer independently, then see each other's answers and revise, for R rounds, then you aggregate.

```
  round 0:  A₁ ──▶ answer₁      A₂ ──▶ answer₂      A₃ ──▶ answer₃   (independent!)
  round 1:  each sees all answers + critiques, revises
  round 2:  ...
  aggregate: majority vote | judge model | highest-confidence

  COST = N × (R+1) model calls, plus context growth per round
  reported: 2.1x-3.4x token multiplier over isolated self-correction, for
  accuracy statistically comparable to or WORSE than non-communicative baselines
  (7-8B instruction-tuned class)
```

Du et al. (2023) introduced this as "Society of Minds" multiagent debate and reported gains on factuality and reasoning. Later controlled work is much less kind, naming three failure modes:

- **Sycophantic conformity** — agents abandon a correct independent answer to agree with a confident peer. Symptom in a trace: round-0 diversity collapsing to unanimity by round 1 regardless of correctness.
- **Contextual fragility** — the result depends heavily on presentation order and phrasing of peers' answers.
- **Consensus collapse** — everyone converges early, so extra rounds cost tokens and change nothing.

The practical position: **debate's measurable value comes from independence and aggregation, not from the conversation.** So if you want the benefit, run N independent samples and aggregate by vote or judge — self-consistency — and skip the cross-talk. If you do debate, enforce diversity structurally (different models, different prompts, an explicitly assigned devil's advocate) and cap rounds at 2, because round 3 almost never changes the answer and always costs.

The one variant that reliably earns its keep is **asymmetric critique**: a *separate* verifier agent with a different prompt and a checklist, run once over the primary agent's output. That is not debate, it is verification, and MAST's third failure category is precisely "task verification" — so a dedicated verifier is one of the few decompositions with a strong prior in its favour.

---

## When NOT to build a multi-agent system

This is the section that decides the interview. Learn the costs as a list you can recite.

### The five real costs

**1. Routing errors.** Every routing decision is a classification the model can get wrong, and the error is silent: you get a confident answer from the wrong specialist. A supervisor at 92% routing accuracy over three hops is 0.92³ ≈ 78% correct routing, before any worker does anything wrong. This compounds with the per-step reliability arithmetic from `T07-agent-loop-from-scratch`: multi-agent multiplies the number of places a step can fail, and reliability is multiplicative. Symptom to look for: a worker whose most common output is "this isn't my area", or a route-distribution histogram with a long tail into one worker.

**2. Context handoff loss.** This is the one Cognition is right about, and it is structural rather than fixable. Either the whole history crosses (so you have paid for extra agents and got zero context isolation, plus N× the prompt cost), or a summary crosses (so information is lost in a way the receiver cannot detect and cannot ask about). There is no third option. The observable symptom is an agent asking for something it was already told, or confidently answering with a detail that was corrected before the handoff. MAST's second-largest failure category is exactly this: inter-agent misalignment.

**3. Latency multiplication.** Coordination is sequential even when work is parallel. A three-level hierarchy pays three routing calls before any work begins; at ~1.5s per call that is ~4.5s of overhead. Supervisor round-trips add a call per hop. And the wall-clock time of a parallel fan-out is the *slowest* branch, not the average — with 5 subagents at p50 8s and p99 45s, your fan-out's p50 is closer to the branches' p90 than their p50. Fan-out helps throughput of information gathering; it does not help latency.

**4. Cost multiplication.** Anthropic's own multi-agent research system uses roughly **15x the tokens of a normal chat**, and token usage alone explained about 80% of performance variance in their browsing evals — which is a double-edged finding, because it means much of the "multi-agent is better" result is *paying more*, not *organising better*. Debate variants report 2.1x-3.4x multipliers for no reliable gain. Before you decompose, ask whether spending 15x on a single agent (bigger model, more steps, more retries, self-consistency) buys more than spending 15x on coordination. Often it does.

**5. Debugging difficulty.** With one agent, a failure is at a step in one trace. With five, the failure is usually in a *seam*: the subtask instruction was underspecified, the handoff summary dropped a constraint, the supervisor mis-routed, two agents made contradictory assumptions, or a worker succeeded at the wrong task. None of those appear as an error. MAST exists because these traces are hard enough to read that researchers needed a taxonomy and an LLM judge to classify 1,600 of them; the paper's traces average many thousands of lines each. Your on-call engineer will be reading those at 3am.

### The plain statement

**A single agent with good tools beats a poorly decomposed multi-agent system almost always.** MAST's opening claim is that MAS performance gains on popular benchmarks are often minimal, and that the dominant failure categories are system design and inter-agent misalignment — that is, the decomposition itself, not the models. If your multi-agent design is not clearly better than one agent with the union of the tools, it is worse, because you have added five cost centres for no benefit.

The corollary that catches people: **"the agent has too many tools" is not a reason to split.** If tool selection is degrading, the first four fixes are all cheaper than another agent: write better tool descriptions, remove overlapping tools (if a human engineer cannot say definitively which tool applies, the model will not do better), group tools behind a smaller number of higher-level tools, or add a tool-search/retrieval step so only relevant schemas are in context. Splitting into agents to solve tool bloat replaces a selection problem with a routing problem *plus* a handoff problem.

### What actually justifies splitting

Six conditions. You need at least one, and "it makes the diagram look organised" is not among them.

| # | Condition | Test that it applies | Example |
|---|---|---|---|
| 1 | **Parallel, read-heavy, small-output subtasks** | intermediate volume ≫ returned volume, and branches are genuinely independent | breadth-first research: 5 subagents each burn 40k tokens, each returns 1.5k |
| 2 | **Mandatory context isolation** | one workstream's tokens would measurably degrade another's | exploring 400 grep hits should not pollute the main agent's window |
| 3 | **Different permission / trust tier** | tools differ in blast radius and need different approval gates and guardrails | read-only research agent vs an agent that can issue refunds |
| 4 | **Different model / latency tier** | some subtasks are cheap-and-fast, others need the frontier model | Haiku-class classification workers under an Opus-class planner |
| 5 | **Independent deployment ownership** | different teams ship on different cadences with their own SLOs | your agent calling another org's agent over A2A |
| 6 | **Untrusted content quarantine** | a subtask must process content that could contain injection | a summariser agent with no tools reads the scraped page; the main agent never sees raw HTML |

Conditions 3 and 6 are the ones candidates rarely mention and interviewers love, because they are *security* arguments rather than performance arguments. An agent that can spend money should be a separate agent precisely so its tools, its guardrails, and its approval gates can be different. And putting untrusted web content behind a tool-less subagent is one of the genuinely strong architectural mitigations for prompt injection — the injected instruction lands in a context with nothing to attack.

Condition 5 is the one that will matter most in two years, and it is why A2A exists: 150+ organisations, 1.0 in April 2026, signed Agent Cards for cryptographic identity. Cross-organisation agents are multi-agent for reasons that have nothing to do with decomposing your task.

### The decision procedure

```
Can one prompt do it?                              → one prompt.
Are the steps known in advance?                    → a workflow / DAG, not an agent.
Can one agent with the union of tools do it?       → ONE AGENT. Default. Stop here.
   ├─ tool selection degrading?                    → better descriptions, fewer tools,
   │                                                 grouping, tool search. NOT agents.
   └─ context blowing up?                          → truncate at tool → clear → compact
                                                     → ephemeral READ-ONLY subagents
Do you have one of the six conditions?             → split, minimally.
   ├─ start with ORCHESTRATOR + read-only subagents (writes stay single-threaded)
   ├─ add a VERIFIER before you add a second worker (MAST: verification is a top-3 category)
   └─ prove it with an eval against the single-agent baseline BEFORE shipping
```

The last line is the whole discipline. **If you cannot show an eval where the multi-agent version beats the single-agent baseline on the same task set, you have not established that the topology helps** — you have established that you spent more.

---

## Build it from scratch

`labs/py/12-multi-agent/` builds all five against a scripted fake model so costs and outcomes are deterministic:

1. **Baseline single agent** with the union of all tools. Record success rate, tokens, latency, and cost on a 20-task golden set. **Every later step is compared to this number.** This is the point of the lab.
2. **Supervisor** with structured routing (`Route` pydantic model), a hop budget, and route logging. Measure routing accuracy against hand-labelled correct routes. Inject a deliberately ambiguous task set and watch accuracy fall.
3. **Handoff swarm** with `Command(goto=..., graph=PARENT)`. Implement both variants: full-history handoff and summary-only handoff. Measure the information loss on the summary variant with a task whose answer depends on a detail mentioned before the handoff.
4. **Blackboard** with typed slots, optimistic concurrency, and a write journal. Force a lost-update race and assert `Conflict` is raised rather than one write silently winning.
5. **Debate vs self-consistency.** Same N and same rounds, one with cross-talk and one with independent samples plus a vote. Compare accuracy and tokens. The expected result is that self-consistency matches or beats debate at lower cost; if your run disagrees, that is more interesting than the lab and worth writing up.
6. **The comparison table.** Success, tokens, p50/p99 latency, cost per task, for all five plus the baseline. Then answer honestly which one you would ship.

Step 6 is the deliverable. "I built five topologies and the single agent won on four of my six task types" is one of the strongest things you can say in an agent interview.

---

## How it's done in production

| Framework | Topologies | What it adds | Sharp edge |
|---|---|---|---|
| **LangGraph** (+ `langgraph-supervisor`, `langgraph-swarm`) | supervisor, hierarchical, swarm, blackboard-ish via shared state | explicit graph, checkpointing so a multi-agent run resumes, `Command(goto=, graph=PARENT)` handoffs, per-node retry | you own state schema and reducers; shared-state races are yours to prevent |
| **OpenAI Agents SDK** | handoff swarm, agents-as-tools | minimal ceremony, tracing, guardrails | **handoff transfers the full history** (no isolation); input guardrails apply only to the first agent in the chain and output guardrails only to the final producer |
| **Microsoft Agent Framework** | group chat, sequential, concurrent, handoff, magentic | AutoGen + Semantic Kernel merged; 1.0 Python/.NET Apr 2026; telemetry, typed state | new-ish surface; migration paths from both predecessors to keep straight |
| **CrewAI** | role-based crews, hierarchical manager | fastest prototyping of "team" metaphors | role prompts do less work than they appear to; termination and cost are hard to bound |
| **Google ADK** | sequential / parallel / loop agents, hierarchy | compaction built in (Python v1.16.0+), Vertex integration | opinionated |
| **A2A protocol** (Linux Foundation) | cross-organisation | Agent Cards with cryptographic identity, task lifecycle, multi-tenancy; 1.0 Apr 2026, 150+ orgs | it is interop, not orchestration; you still need a topology inside your own boundary |

**Failure modes**

| Symptom | Cause | Fix |
|---|---|---|
| A worker's most common reply is "not my area" | Supervisor misrouting; overlapping worker scopes | Log routes with a `why` field; measure route accuracy against labels; merge overlapping workers |
| Agent asks for information it was already given | Handoff dropped it (summary variant) | Structured handoff note with required fields; pass pointers so the receiver can re-read |
| Agent acts on a detail that was corrected pre-handoff | Handoff carried stale context | Carry the *latest correction* explicitly, as a required field in the handoff payload |
| Cost is 10-15x the single-agent baseline for a small quality gain | Coordination overhead + full-history handoffs | Compare against spending the same budget on one better agent; switch to distilled returns |
| p99 latency exploded after fan-out | Fan-out latency is the slowest branch, not the average | Per-branch deadlines with partial results; cap fan-out width |
| Two agents wrote contradictory values | Shared mutable state without concurrency control | Typed slots + optimistic concurrency + write journal; or keep writes single-threaded |
| Group chat never terminates | No termination predicate; agents politely continue | Explicit max rounds *and* a structured "done" signal; never rely on conversational termination |
| Debate converges to a confidently wrong answer | Sycophantic conformity / consensus collapse | Enforce independence in round 0; different models/prompts; cap at 2 rounds; or use self-consistency instead |
| A guardrail did not fire on a worker | SDK semantics: input guardrails apply to the first agent only | Guardrail at every boundary, or keep untrusted input confined to one entry agent |
| Nobody can explain why the run failed | No cross-agent trace correlation | One trace id across all agents; span per agent with the subtask, the return, and the token/cost attribution |
| Injected instruction from a scraped page caused a tool call | Untrusted content entered an agent with tools | Quarantine pattern: tool-less summariser reads raw content, main agent sees only its output |

**Observability is different here.** One trace id must span every agent, with a span per agent invocation carrying the subtask in, the structured return out, tokens, cost, and outcome. Add two metrics that only exist in multi-agent systems: **route distribution and route accuracy**, and **handoff count per run**. A rising handoff count is the earliest signal that agents are ping-ponging, which is the multi-agent equivalent of the no-progress loop.

---

## Tradeoffs & when NOT to use it

- **Default to one agent.** Not as a rhetorical device — as the actual default that requires evidence to override. One agent with a well-curated tool set, good tool descriptions, compaction, and read-only subagents for exploration covers the large majority of production use cases.
- **Never split to fix tool bloat.** Fix descriptions, remove overlap, group, or add tool search. Splitting converts a selection problem into a routing problem plus a handoff problem.
- **Never split along your org chart.** "We have a data team and a support team, so we need a data agent and a support agent" is Conway's law applied where it does not belong. Split along *context and permission boundaries*, which sometimes coincide with team boundaries and often don't.
- **Do not let more than one agent write.** The single-writer principle is the most durable practical finding in this area: extra agents should contribute intelligence, not actions. Concurrent writers give you conflicting actions with no serialisation point and no way to reason about the final state.
- **Do not use debate as a default quality mechanism.** The measurable benefit comes from independence and aggregation; self-consistency gets most of it at a fraction of the cost. If you want a second opinion, use an asymmetric verifier with a checklist, once.
- **Do not use a blackboard with untyped shared text.** Typed slots, versions, and a journal, or use a supervisor.
- **Multi-agent does not fix a bad single agent.** If your one agent fails because tools are unreliable, prompts are vague, or evals don't exist, five agents fail the same way in five places and you now cannot see it. Fix the fundamentals first; this is MAST's central finding restated.
- **The honest counter-argument.** Anthropic's Research feature is genuinely better as a multi-agent system, by 90.2% on research tasks, and that is not marketing — it is the correct topology for breadth-first search where the total information exceeds one context window and the branches are independent. So the doctrinaire anti-multi-agent position is also wrong. The discriminating variable is task shape: **parallel breadth with independent branches and small distilled returns favours decomposition; sequential depth with shared evolving context favours one agent.** Say that sentence and you have answered the question.

---

## Interview questions

### Q1 — Design a multi-agent system for automating customer support.
**Testing:** whether you accept the premise. This is the trap.
**Answer:** Push back first, then design. Start with one agent: tools for ticket lookup, order status, knowledge-base search, refund issuance, and escalation; good descriptions; compaction; a step budget. Measure it. Then split only where a condition demands it, and here two do. First, **permission tier** — refunds and account changes have a different blast radius, so they belong behind a separate agent with its own guardrails and an approval gate for amounts over a threshold. Second, **untrusted content quarantine** — if we ingest customer-supplied attachments or scraped pages, a tool-less summariser agent should read them so an injected instruction lands somewhere with nothing to attack. Everything else stays one agent. Not a researcher, a writer, and a critic.
**Follow-up trap:** *"That sounds like you're avoiding the question."* — I'm answering the version that survives production. The specific costs of the version you asked for are: routing errors (silently confident answers from the wrong specialist), handoff loss (either the whole history crosses so you got no isolation, or a summary crosses and loses something undetectably), latency stacking from sequential routing calls, roughly 10-15x cost, and failures that live in seams rather than in any agent. MAST annotated 1,600+ traces across 7 frameworks and found design and inter-agent misalignment dominate, not model capability. If you want the multi-agent version, I'd want an eval showing it beats the single-agent baseline before it ships.

### Q2 — Supervisor vs swarm. Compare and contrast, and when do you choose each?
**Answer:** Supervisor centralises routing: one node decides, every decision appears in one trace, and workers never talk to each other. Swarm distributes it: agents hold handoff tools and transfer control directly, so there is no intermediary, fewer LLM calls, and lower latency. The tradeoff is exactly observability against speed. Supervisor when you will have to debug this on call, when you need cost attribution per decision, or when routing needs to be a measurable component. Swarm when the handoff graph is small and mostly linear — a triage funnel — and latency matters. In LangGraph terms both are the same primitive: handoffs are `Command(goto=..., graph=Command.PARENT)`; the supervisor is just the case where every `goto` points back to one node.
**Follow-up trap:** *"What crosses the boundary on a handoff?"* — framework-dependent and this is where people get caught. In the OpenAI Agents SDK a handoff transfers the entire message history, so the receiving agent sees everything as if it had been there — convenient, but you get zero context isolation and you pay full prompt cost at every agent. In LangGraph you control the update payload, so isolation is possible but the summary becomes a lossy artefact you must engineer with required fields. Also SDK-specific and security-relevant: input guardrails apply only to the first agent in a handoff chain and output guardrails only to the final producer, so a mid-chain agent can be unguarded.

### Q3 — When is a single agent better than a multi-agent system?
**Testing:** the core of the module.
**Answer:** Almost always, unless a specific condition applies. The costs of decomposition are routing errors that compound multiplicatively, context handoff loss with no third option between "everything crosses" and "something is lost", latency multiplication because coordination is sequential and fan-out latency is the slowest branch, cost multiplication of roughly 15x in Anthropic's own reported system, and failures that live in seams and don't surface as errors. MAST's headline is that MAS gains on popular benchmarks are often minimal and the dominant failure categories are system design and inter-agent misalignment. So the default is one agent with the union of the tools, and the burden of proof is on the split.
**Follow-up trap:** *"So you'd never build one?"* — no, and refusing all decomposition is also wrong. Six conditions justify it: parallel read-heavy subtasks whose intermediate volume vastly exceeds their output; mandatory context isolation; a different permission or trust tier; a different model or latency tier; independent deployment ownership across teams or organisations, which is what A2A is for; and quarantining untrusted content behind a tool-less agent. Anthropic's Research feature satisfies the first two and beat single-agent Opus 4 by 90.2%. The discriminator is task shape: parallel breadth with independent branches favours splitting, sequential depth with shared evolving context favours one agent.

### Q4 — My agent has 30 tools and picks the wrong one. Should I split it into specialists?
**Answer:** No, not first. Four cheaper fixes, in order. Rewrite tool descriptions with explicit "use this when / do not use this when" guidance. Remove overlap — Anthropic's guidance is blunt here: if a human engineer cannot definitively say which tool applies in a situation, the agent will not do better, so overlapping tools are a design bug. Group fine-grained tools behind fewer higher-level ones. Add a tool-search step so only relevant schemas are in context. Splitting into agents replaces a selection problem with a routing problem *plus* a handoff problem, and the routing problem has the same failure mode as tool selection with more machinery around it.
**Follow-up trap:** *"When does tool count genuinely force a split?"* — when the tools differ in *permission tier* rather than in count. Thirty read-only tools is a description problem. Three read tools plus one tool that can move money is an architecture problem, because that tool needs different guardrails, a different approval gate, and probably a different audit trail. Split on blast radius, not on cardinality.

### Q5 — Explain the blackboard pattern and when you'd use it.
**Answer:** Agents do not address each other; they read from and write to a shared, typed, versioned store, and a controller schedules whichever agent's preconditions are satisfied. It comes from HEARSAY-II in the 1970s-80s, where independent knowledge sources posted hypotheses to shared state. It fits work that is incremental and non-linear — several agents contributing evidence toward hypotheses where the order is data-dependent rather than plannable — and it gives an excellent audit trail via the write journal. The critical implementation detail is that the slots must be *typed* with versions and optimistic concurrency. An untyped shared scratchpad is the worst option available, because every agent rewrites everyone else's work and no change is attributable.
**Follow-up trap:** *"What's the named failure mode?"* — lost update. Two agents read hypothesis v3, both write, one silently wins, and the trace shows both succeeding, so the contradiction surfaces much later as a wrong answer with no obvious cause. Optimistic concurrency with an explicit `Conflict` exception makes it visible at write time. And the deeper mitigation is the single-writer principle: prefer a design where only one agent mutates a given slot.

### Q6 — Does multi-agent debate work?
**Answer:** Less well than the 2023 literature suggested. Du et al.'s "Society of Minds" reported gains on factuality and reasoning, but controlled follow-ups in the 7-8B instruction-tuned class find homogeneous unguided debate imposes a 2.1x-3.4x token multiplier for accuracy statistically comparable to or worse than isolated self-correction, with three named failure modes: sycophantic conformity, where an agent abandons a correct answer to agree with a confident peer; contextual fragility, where results depend on presentation order; and consensus collapse, where everyone converges early so extra rounds cost tokens and change nothing. My read is that the measurable value comes from *independence and aggregation*, not from the conversation, so self-consistency — N independent samples plus a vote or judge — captures most of the benefit at lower cost.
**Follow-up trap:** *"When would you use debate anyway?"* — when I can enforce genuine diversity structurally: different models, materially different prompts, and an explicitly assigned devil's advocate, capped at two rounds. And the variant that reliably earns its keep isn't debate at all, it's asymmetric verification — one separate verifier with a checklist and a different prompt, run once. MAST's third failure category is task verification, so a dedicated verifier has a stronger prior than any symmetric debate scheme.

### Q7 — Your multi-agent system is 12x the cost of the single-agent version for a 5% quality gain. What do you do?
**Answer:** Kill it, or justify it on unit economics rather than on architecture. The comparison that matters is not multi-agent versus single-agent, it is *this multi-agent system versus one agent given the same 12x budget* — a bigger model, more steps, more retries, self-consistency over 5 samples, better retrieval. That comparison is usually not run and often reverses the conclusion, which is why Anthropic's finding that token usage alone explains ~80% of performance variance on browsing evals is double-edged: much of the multi-agent gain is *paying more*, not *organising better*. If the task genuinely justifies 12x — high-value research where analyst hours dominate token cost — then it's fine and you say so with the ROI arithmetic. If it's a support chat, it's not.
**Follow-up trap:** *"Where would you look first for the cost?"* — full-history handoffs. If the framework transfers the whole conversation to each agent, you are paying N× for the same prefix and getting no isolation benefit. Switch to distilled returns with a token budget and pointers. Second: routing overhead, which is one LLM call per hop and is pure tax. Third: unbounded rounds in any conversational component.

### Q8 — How do you debug a multi-agent failure?
**Answer:** You cannot, unless you built for it. Requirements: one trace id spanning every agent; a span per agent invocation carrying the subtask in, the structured return out, tokens, cost, and outcome; the routing decision logged with the model's stated reason; and the handoff payload logged verbatim. Then the diagnosis is a classification, and MAST's three categories are a good checklist: was it a specification/design issue (the subtask was underspecified, the worker's scope overlapped another's), inter-agent misalignment (the handoff dropped or distorted context, agents made contradictory assumptions), or verification failure (nobody checked the output and a plausible-but-wrong result propagated)? Two multi-agent-specific metrics: route accuracy against labels, and handoff count per run — a rising handoff count is the earliest signal of ping-ponging.
**Follow-up trap:** *"Which category is most common in your experience?"* — the seams, which is design plus misalignment. That matches MAST, whose whole premise is that failures require better orchestration rather than bigger models. Practically it means most of my debugging time goes into the subtask instruction and the handoff contract, not into the agents' prompts.

### Q9 — What is the single-writer principle and why does it matter?
**Answer:** Only one agent mutates state; every other agent contributes information. It comes out of the same 2025 debate as "Don't Build Multi-Agents": multi-agent systems work best when writes stay single-threaded and the additional agents contribute intelligence rather than actions. It matters because concurrent writers give you conflicting actions with no serialisation point, no way to reason about final state, and non-idempotent side effects that may have partially applied. It also simplifies safety enormously: there is exactly one place where an approval gate, an idempotency key, and an audit record need to live.
**Follow-up trap:** *"What if the parallel work genuinely needs to write?"* — then serialise the writes rather than the thinking. Workers *propose* structured changes; the orchestrator validates, resolves conflicts, and applies them in a defined order. That is the blackboard-with-a-controller shape, and it keeps parallel exploration while keeping one writer. If even that is impossible, you need distributed-systems machinery — optimistic concurrency, idempotency keys, compensating transactions — and at that point ask whether a durable workflow engine with LLM activities is the better abstraction than an agent topology.

### Q10 — Orchestration or choreography for a multi-agent system?
**Testing:** whether you can map agent topologies onto distributed-systems vocabulary, which is where senior candidates get an edge.
**Answer:** They map directly: orchestration is the supervisor, choreography is the swarm. And the tradeoffs transfer wholesale from microservices. Orchestration gives you a single place that knows the whole plan, so control flow is explicit, testable, and observable, at the cost of a bottleneck and a coupling point. Choreography gives you autonomy and lower latency at the cost of emergent behaviour nobody designed and a control flow you must reconstruct from traces. The LLM-specific twist is that the "router" in orchestration is a probabilistic classifier that can be wrong, which is worse than a deterministic orchestrator — so the case for choreography is weaker here than in microservices, not stronger, because you lose the one place where you could have measured routing accuracy.
**Follow-up trap:** *"Given that, why does anyone build swarms?"* — latency and cost: no intermediary means fewer LLM calls per transfer, which matters in voice and other interactive settings where a supervisor round-trip is a perceptible pause. It is a real engineering reason, and it is the only one I would accept.

### Q11 — Design an agent system that spans two companies.
**Testing:** whether you know the one case where multi-agent is not a choice.
**Answer:** This is where multi-agent is forced, and it is an interop problem rather than a decomposition problem. A2A is the relevant standard: donated to the Linux Foundation, 1.0 in April 2026, 150+ organisations, SDKs in five languages, with signed Agent Cards giving cryptographic identity so you can verify who you are talking to, plus a defined task lifecycle and multi-tenancy support. Inside my own boundary I still run one agent or an orchestrator with read-only subagents; the remote agent is, from my side, a tool with a network boundary, an SLA, an auth story, and an untrusted output. Which means everything from resilience applies — timeouts, retries with idempotency keys, circuit breakers — plus treating the remote agent's output as untrusted content that must not be able to drive my tool calls directly.
**Follow-up trap:** *"How is A2A different from MCP?"* — different layer. MCP connects an agent to *tools and data*; A2A connects an agent to *another agent* that has its own reasoning, its own opacity, and its own goals. The practical difference is that a tool returns data you asked for, whereas a remote agent returns something it decided to produce, which is why identity, task lifecycle, and output distrust are first-class in A2A and largely absent from MCP.

### Q12 — How would you prove your multi-agent design was the right call?
**Answer:** A single-agent baseline on the same golden task set, with the same tools, measured on success rate, tokens, p50 and p99 latency, and cost per task. Then the multi-agent version on the same set. Then the comparison people skip: the single agent given the *same budget* as the multi-agent system — bigger model, more steps, self-consistency — because if that wins, the topology contributed nothing and I was just spending more. I'd also break results down by task shape, because I expect decomposition to win specifically on parallel-breadth tasks with independent branches and lose on sequential-depth tasks with shared evolving context, and if the breakdown doesn't show that pattern I would distrust my own eval.
**Follow-up trap:** *"You don't have time for all that. What's the minimum?"* — the single-agent baseline. One number, on the same tasks. It is a day of work and it is the difference between an architecture decision and a preference. Shipping a multi-agent system with no single-agent baseline is the specific mistake that MAST is a 1,600-trace catalogue of.

### Q13 — Two agents disagree on a fact. What happens?
**Answer:** By default something bad and invisible: whichever result the orchestrator read last, or whichever the synthesis step happened to weight, wins silently. So it has to be designed. Three rules. Structured returns with confidence and evidence pointers, so disagreement is *detectable* rather than buried in prose. An explicit conflict path in the orchestrator: identify the contradiction, and either send both agents the other's evidence for one reconciliation round, or apply a documented tiebreak such as preferring the agent whose evidence is a primary source. And when it cannot be resolved, **surface the conflict to the user rather than silently picking**, because a confident wrong answer is worse than a flagged uncertainty.
**Follow-up trap:** *"Isn't that just debate?"* — one bounded reconciliation round over a *detected* contradiction is targeted and cheap. Debate is unconditional cross-talk over every question, which is where the 2.1x-3.4x token multiplier and the sycophantic-conformity failure come from. The difference is that reconciliation is triggered by evidence of disagreement, not run by default.

---

## Red flags that fail you

- Drawing a researcher, a writer, and a critic in response to any prompt.
- No single-agent baseline, and no plan to build one.
- Splitting to solve tool bloat.
- Splitting along the org chart.
- Letting more than one agent write.
- Not knowing what crosses the boundary on a handoff in the framework you named.
- Presenting multi-agent debate as an established quality win.
- No termination condition on a conversational pattern like `GroupChat`.
- Treating a remote agent's output as trusted input to your own tool calls.
- Quoting the 90.2% figure without the 15x token cost, or vice versa.
- Being unable to name the five costs: routing errors, handoff loss, latency multiplication, cost multiplication, debugging difficulty.
- "Multi-agent will fix our reliability problem" when the single agent's tools are unreliable.

## Cheat card

```
TWO AXES GENERATE EVERYTHING
  who decides next: central (supervisor) vs distributed (swarm)
  what crosses:     full history vs distilled summary
  → orchestrator + DISTILLED read-only subagents is the shape that usually wins

FIVE TOPOLOGIES
  SUPERVISOR    one router · all decisions in one trace · +1 LLM call per hop
                4 workers ≈ 9 model calls (4 route + 4 work + 1 synthesise)
  HIERARCHICAL  supervisor of supervisors · split ONLY on permission/model/ownership
                cost: ~1.5s routing latency PER LEVEL before any work starts
  SWARM         peer handoff · Command(goto=X, graph=Command.PARENT)
                faster/cheaper · no single place to look · OpenAI SDK sends FULL history
  BLACKBOARD    typed+versioned slots, optimistic concurrency, write journal
                failure = LOST UPDATE (both writes "succeed", one vanishes)
  DEBATE        N agents × (R+1) rounds · 2.1-3.4x tokens for ≈ or WORSE accuracy
                sycophantic conformity · contextual fragility · consensus collapse
                → prefer SELF-CONSISTENCY (independent samples + vote) or ONE VERIFIER

THE FIVE COSTS (recite these unprompted)
  1 routing errors      0.92³ ≈ 78% over 3 hops, silent, confident wrong specialist
  2 handoff loss        full history = no isolation + N× cost; summary = undetectable loss
  3 latency mult.       coordination is sequential; fan-out p50 ≈ branches' p90
  4 cost mult.          Anthropic's own system ≈ 15x tokens of a normal chat
  5 debugging           failure lives in the SEAM; MAST needed a taxonomy for 1,600 traces

THE PLAIN STATEMENT
  A single agent with good tools beats a poorly decomposed MAS almost always.
  MAST (arXiv 2503.13657, 1600+ traces / 7 frameworks, 14 modes / 3 categories):
    system design issues · inter-agent misalignment · task verification
    → failures are DESIGN, not model capability

WHAT JUSTIFIES SPLITTING (need ≥1)
  1 parallel read-heavy subtasks, big intermediate → small return (40k in, 1.5k out)
  2 mandatory context isolation
  3 different PERMISSION/trust tier      ← candidates forget; interviewers love
  4 different model/latency tier
  5 independent deployment ownership     ← A2A: LF, 1.0 Apr 2026, 150+ orgs
  6 untrusted content quarantine         ← tool-less summariser reads the raw page
  NOT reasons: 30 tools · the org chart · the diagram looks tidy

NOT A FIX FOR TOOL BLOAT
  better descriptions → remove overlap → group → tool search.  THEN maybe agents.

SINGLE-WRITER PRINCIPLE
  one agent mutates; others contribute intelligence, not actions
  parallel writes needed? workers PROPOSE, orchestrator validates + applies in order

THE EVIDENCE ON BOTH SIDES
  Anthropic Research: +90.2% vs single-agent Opus 4 · ~15x tokens
    tokens alone explain ~80% of perf variance ← so part of the "win" is just spending
  Cognition "Don't Build Multi-Agents" (Jun 2025): single-threaded + compression model
  synthesis: parallel BREADTH w/ independent branches → split
             sequential DEPTH w/ shared evolving context → one agent

DECISION ORDER
  one prompt → workflow/DAG → ONE AGENT (default) → fix tools/context
  → orchestrator + read-only subagents → add a VERIFIER → prove with an eval
  no single-agent baseline = no architecture decision, just a bigger bill
```

## Sources

- [Why Do Multi-Agent LLM Systems Fail?](https://arxiv.org/abs/2503.13657) — Cemri et al., v3 Oct 2025; MAST taxonomy, 14 modes in 3 categories, MAST-Data 1,600+ traces across 7 frameworks, taxonomy derived from 150 traces at κ=0.88; accessed 2026-07-26
- [Anthropic — How we built our multi-agent research system](https://www.anthropic.com/engineering/multi-agent-research-system) — orchestrator/subagent design, 90.2% over single-agent Opus 4, ~15x tokens, token usage explaining ~80% of browsing-eval variance; accessed 2026-07-26
- [Cognition — Don't Build Multi-Agents](https://cognition.com/blog/dont-build-multi-agents) — single-threaded linear agents, compression model, handoff loss, single-writer; June 2025, accessed 2026-07-26
- [Anthropic — Effective context engineering for AI agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) — subagents returning 1,000-2,000 distilled tokens; tool-set bloat guidance; accessed 2026-07-26
- [OpenAI Agents SDK — Handoffs](https://openai.github.io/openai-agents-python/handoffs/) and [Guardrails](https://openai.github.io/openai-agents-python/guardrails/) — full-history handoff semantics; input guardrails on the first agent only, output guardrails on the final producer; accessed 2026-07-26
- [langgraph-supervisor (LangChain reference)](https://reference.langchain.com/python/langgraph-supervisor/) — `Command(goto=..., graph=Command.PARENT)` handoff mechanics; accessed 2026-07-26
- [Microsoft Agent Framework overview](https://learn.microsoft.com/en-us/agent-framework/overview/) — AutoGen + Semantic Kernel convergence; public preview Oct 2025, 1.0 for Python/.NET Apr 2026; accessed 2026-07-26
- [Linux Foundation — A2A Protocol surpasses 150 organizations](https://www.linuxfoundation.org/press/a2a-protocol-surpasses-150-organizations-lands-in-major-cloud-platforms-and-sees-enterprise-production-use-in-first-year) — 1.0 April 2026, signed Agent Cards, five language SDKs; accessed 2026-07-26
- [Improving Factuality and Reasoning in Language Models through Multiagent Debate](https://arxiv.org/abs/2305.14325) — Du et al., 2023; the "Society of Minds" debate result; accessed 2026-07-26
- [The Cost of Consensus: Isolated Self-Correction Prevails Over Unguided Homogeneous Multi-Agent Debate](https://arxiv.org/abs/2605.00914) — 2.1x-3.4x token multiplier, sycophantic conformity, contextual fragility, consensus collapse; accessed 2026-07-26

## Changelog
- 2026-07-26 — created
