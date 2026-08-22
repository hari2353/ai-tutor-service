# Framework Matrix: LangGraph vs ADK vs OpenAI SDK vs CrewAI vs AutoGen

> **Track:** T07 Agentic AI · **Time:** 2.0h · **Prereqs:** none · **Updated:** 2026-08-01
> **Module id:** `T07-framework-matrix` · **Tags:** framework,tradeoffs

## The 30-second version

Six real options exist for building an agent in 2026, not five: LangGraph, Google's ADK, OpenAI's Agents SDK, CrewAI, AutoGen (now effectively frozen), and hand-rolled. None of them is "the best framework" because they optimize for different axes and the honest matrix has losers on every row. LangGraph wins when you need durable, checkpointed, inspectable state machines and you can absorb its migration cadence. OpenAI's Agents SDK wins when you want the thinnest possible loop with native tracing and you're comfortable being provider-adjacent. Google's ADK wins inside a Google Cloud shop that wants multi-agent orchestration and Vertex AI's managed session/memory layer, and is a poor choice outside that shop. CrewAI wins for fast prototyping of role-based crews and loses the moment your workflow needs real branching instead of sequential or hierarchical delegation. AutoGen no longer wins anything — Microsoft put it in maintenance mode in 2025 and told the community to use Agent Framework instead, so recommending AutoGen for new work in 2026 is a stale answer. And hand-rolled wins more often than people admit: a three-to-ten-step loop with one model and a fixed tool set is forty lines, and every framework here is negative value at that scale. The single most important interview move on this topic is naming where each framework is the *wrong* choice before anyone asks.

## Why this gets asked

Because framework choice is one of the few architecture decisions in this space with a real, durable cost — you're picking a migration cadence, a debugging story, and a lock-in profile for the life of the project, and most candidates have used exactly one framework and will defend it reflexively. The interviewer has usually watched a team pick a framework because it was trending on GitHub, hit its specific limitation eighteen months in (CrewAI's rigid process model on a workflow that turned out to need real branching; AutoGen going quiet while the roadmap moved to a different product; LangGraph's third streaming format in fifteen months breaking a UI integration), and paid a rewrite. They want to know whether you evaluate frameworks against the actual shape of the problem or against what's popular, and whether you'll say "hand-rolled is right here" when it's true instead of reaching for a name-brand dependency to look sophisticated.

---

## Lineage: past → present → future

**What came before.** The 2023 generation — `AgentExecutor`, the first CrewAI and AutoGen releases, ChatGPT plugins — all shared one property: a loop with no inspectable state, no durability, and safety logic living in prose. The pain that killed that generation was uniform across frameworks: a failure at step seven meant a full restart with no reproducibility, and "the agent did something destructive" had no permission layer to point to, only a system prompt. `T07-agent-loop-from-scratch` and `T07-harness-engineering` cover the general version of this; the framework-specific version is that every framework built after 2024 is, in some sense, a response to that same failure — LangGraph answered with checkpointed state machines, OpenAI's Agents SDK answered by making the loop thin enough that you own the hard parts explicitly, ADK answered by bundling Google's session and memory services underneath a multi-agent-first API, and CrewAI answered by giving non-framework engineers a role-based mental model (a "crew" of named agents) that reads like an org chart instead of a graph.

**Where it stands now.** The field split into two camps rather than converging, and both are legitimate. The *structure camp* (LangGraph, ADK) argues that declaring topology explicitly is what makes an agent auditable, resumable, and debuggable at the state level, and it is winning the durability and observability axes on the evidence: checkpointing, time-travel, and per-node retry policies are mature in both. The *thin-loop camp* (OpenAI Agents SDK, and hand-rolled by extension) argues that scaffolding encodes assumptions about model capability that expire, per the Bitter Lesson framing `T07-harness-engineering` covers in depth, and that a good loop with minimal ceremony ages better as models improve. CrewAI sits awkwardly between the two: it has real production adoption (an enterprise tier shipped March 2026, roughly 45,400 GitHub stars at v1.10.1) and the fastest time-to-a-working-prototype of anything on this list, but its process model (sequential or hierarchical crews) is a genuine ceiling, not a starting point you grow out of gracefully — teams hit it and either accept the limitation or rewrite. AutoGen is the clearest resolved case on this list: Microsoft placed it and Semantic Kernel into maintenance mode and shipped **Microsoft Agent Framework** (public preview October 2025, GA 1.0 on 3 April 2026) as the actual successor, merging AutoGen's multi-agent orchestration with Semantic Kernel's enterprise state management, telemetry, and type safety. Recommending AutoGen for a new project past that date without naming Agent Framework is answering with 2024 information.

**Where it's heading.** High confidence: the field consolidates around two or three frameworks per major cloud/model vendor rather than staying fragmented, because every vendor now has exactly one framework it tells customers to use (OpenAI → Agents SDK, Google → ADK, Microsoft → Agent Framework, Anthropic → Claude Agent SDK adjacent to LangGraph's ecosystem), and independent frameworks without a vendor behind them (CrewAI) have to compete on developer experience alone. Medium confidence: the durability and observability features that differentiate LangGraph today (checkpointing, per-node policies, typed event logs) become table stakes across all of them within a year or two, the way Microsoft Agent Framework's `HarnessAgent` already ships most of them out of the box (`T07-harness-engineering`). Speculative: any claim that one framework has "won." The benchmark evidence people cite (framework choice moving agent benchmark scores by up to 30 percentage points on identical models) actually argues the opposite — it means the graph design and tool set dominate the framework brand, which is a reason to evaluate against your specific workload rather than trust a leaderboard.

---

## Mental model

Six boxes, one question each: **what does this framework assume you already have, and what does it refuse to give you?**

```
                    LOOP        DURABLE     STREAMING   HITL        MULTI-AGENT  LOCK-IN
                    CONTROL     CHECKPOINT              PRIMITIVE   PRIMITIVES
  ─────────────────────────────────────────────────────────────────────────────────────
  LangGraph         explicit    mature      3 formats   interrupt() Send/subgraph  low
                    graph       (Pregel)    in 15mo     + resume    /Command       (OSS)
  ─────────────────────────────────────────────────────────────────────────────────────
  Google ADK        agent-      Vertex AI   Bidi        session-    core           HIGH
                    first       Agent       streaming   based       abstraction    (GCP)
                    (implicit)  Engine      (native)    pause                      
  ─────────────────────────────────────────────────────────────────────────────────────
  OpenAI Agents     thin loop,  none        native      guardrail   handoffs       medium
  SDK               you own it  native      (Responses  fail-fast   (agent-as-     (OpenAI
                                            API)                    tool)          models)
  ─────────────────────────────────────────────────────────────────────────────────────
  CrewAI            sequential/ shallow     partial     limited     CORE           low
                    hierarchical            (v2 SDK)                abstraction    (OSS, but
                    "crew"                                                        rigid)
  ─────────────────────────────────────────────────────────────────────────────────────
  AutoGen           conversat-  shallow     partial     limited     core           MAINTENANCE
  (frozen)          ional turn-                                     abstraction    MODE — use
                    taking                                                        Agent Fwk
  ─────────────────────────────────────────────────────────────────────────────────────
  Hand-rolled       total       whatever    whatever    whatever    whatever you   zero
                    (you write  you build   you build   you build   build          (yours)
                    it)
```

The one thing to internalize: **every row in this table is a place where a framework made a decision so you don't have to, and every one of those decisions is wrong for some workload.** The senior move is matching the row to the actual requirement, not defaulting to whichever framework you learned first.

---

## How it actually works

### Loop control: explicit graph vs thin loop vs conversational turn-taking

**LangGraph** makes topology the artifact: you declare a `StateGraph` with nodes, edges, and reducers (`T07-langgraph-core`), and the runtime executes it as Pregel super-steps. This is the most control of anything on the list, and it's control you pay for in ceremony — a linear three-step pipeline in LangGraph is a state schema, two node functions, and a compile step for something that's a function call.

**OpenAI's Agents SDK** deliberately minimizes abstractions: an `Agent` (instructions, tools, handoffs), a `Runner` that executes the loop until the model returns without a tool call or `max_turns` is hit, and that's most of the mental model. The tradeoff is that you own everything the loop doesn't give you — budgets beyond a turn cap, compaction, progress detection — which is exactly `T07-loop-engineering`'s territory, and the SDK doesn't pretend otherwise.

**Google's ADK** treats orchestration as a first-class multi-agent primitive from the start rather than something you build on top of a single-agent loop: `LlmAgent`, `SequentialAgent`, `ParallelAgent`, and `LoopAgent` compose into a tree, and a single agent is really the degenerate case of a one-node tree. This is the opposite design bet from OpenAI's SDK — ADK assumes you'll want delegation and builds the primitive in up front.

**CrewAI** models a "crew" as named agents with roles, goals, and backstories, coordinated by a `Process` that's either `sequential` (agents run in a fixed order, each seeing prior output) or `hierarchical` (a manager agent delegates). This is the most opinionated loop shape on the list, and it's opinionated in a way that maps well onto human-organization mental models, which is exactly why it prototypes fast — and exactly why it hits a ceiling the moment a workflow needs conditional branching a sequential or hierarchical structure can't express.

**AutoGen** models multi-agent as conversational turn-taking between `ConversableAgent` instances, which is a genuinely different mental model (agents "talk" to each other in a shared conversation) from all the others on this list. It's elegant for negotiation-style tasks and awkward for anything with a real DAG shape, which the graph-based frameworks express more directly.

### Durability: who survives a crash at step seven

This is the axis with the sharpest split. **LangGraph** checkpoints at every super-step boundary by default once you supply a checkpointer, and resume means "replay from the last completed super-step," not "restart" (`T07-langgraph-core`, `T07-langgraph-durable`). **Google ADK** delegates this to Vertex AI Agent Engine's `SessionService` in production — the local `InMemorySessionService` is explicitly a development-only trap, and the durability story is real but tied to deploying on Google Cloud. **OpenAI's Agents SDK** has no native checkpointing across process restarts; `Sessions` give you persistent conversational memory (with SQLite, Redis, or SQLAlchemy backends) but that's state *within* a live run, not resumability *across* a crash — if you need durable execution with this SDK, you build it yourself or put it behind Temporal. **CrewAI** and **AutoGen** both have shallow durability stories relative to LangGraph and ADK; CrewAI's state persistence is workflow-output-level rather than step-level, and AutoGen's is essentially whatever you build around `ConversableAgent`'s message history.

At 85% per-step reliability, a ten-step run completes about 20% of the time (`T07-agent-loop-from-scratch`), which is the arithmetic that makes this axis matter more than it looks like it should in a feature comparison table. If your task is genuinely multi-step and you pick a framework with a shallow durability story, you are committing to hand-rolling the exact thing LangGraph or ADK would have given you.

### Streaming

**LangGraph** exposes seven `stream_mode`s and has been through three wire formats in fifteen months (v1 tuples, v2 unified `StreamPart`, v3 typed projections — `T07-langgraph-core`), which is powerful and also the sharpest churn risk on this list; code written against the streaming surface has migrated twice already. **Google ADK** ships native bidirectional streaming (`Bidi-streaming`) for real-time multimodal interaction (text, audio, video) as a first-class, production-oriented feature, which is a genuine differentiator if your product is voice or live video rather than request-response chat. **OpenAI's Agents SDK** streams natively off the Responses API, which is straightforward token-and-event streaming without the multi-format churn LangGraph has had. **CrewAI** and **AutoGen** both have partial streaming support that lags the other three; treat either as the wrong choice if token-by-token UX is a hard product requirement.

### Human-in-the-loop

**LangGraph**'s `interrupt()` plus a durable checkpointer is the most composable primitive here — it suspends to storage at an arbitrary point and `Command(resume=...)` continues, which is what `T07-human-oversight`'s gate placement model assumes underneath it. **Google ADK** supports session-based pause points tied into its managed session service, which is coherent within the GCP deployment model but less portable outside it. **OpenAI's Agents SDK** guardrails run input/output validation in parallel with execution and fail fast, which is a real safety mechanism but a narrower one than a full approval-and-resume gate — it stops a bad output, it doesn't durably pause a multi-day approval the way `interrupt()` does. **CrewAI** and **AutoGen** both have limited native HITL relative to the other three; CrewAI has added human-input tool patterns but nothing as composable as `interrupt()`, and AutoGen's HITL story was always closer to "insert a human as another `ConversableAgent`," which works for synchronous review and not for a durable multi-day approval.

### Multi-agent primitives

**Google ADK** and **CrewAI** both treat multi-agent as *the* core abstraction — ADK via composable agent trees (`Sequential`/`Parallel`/`Loop` agents), CrewAI via named crews and a `Process`. **AutoGen**'s conversational model is also multi-agent-first, just with a different mental model (message-passing between peers rather than a tree or a role hierarchy). **LangGraph** and **OpenAI's Agents SDK** both treat multi-agent as composition on top of a single-agent primitive — subgraphs and `Send` fan-out in LangGraph, `handoffs` (an agent calling another agent as a tool) in the OpenAI SDK — which is a real design choice, not an omission: it means you don't pay a multi-agent abstraction tax until you actually need one.

### Observability, lock-in, and debugging

**LangGraph** traces natively into LangSmith and exposes `stream_mode="tasks"` for OpenTelemetry-style spans if you're not on LangSmith; it's open source and the lock-in is genuinely low, though the migration cadence (three streaming formats, `create_agent` relocating out of `langgraph` into `langchain`) is its own tax. **Google ADK** ships integrations into observability platforms and is positioned as an execution layer with deployment, monitoring, and eval built in, but almost all of that maturity assumes you deploy on Vertex AI Agent Engine — take ADK off Google Cloud and you're rebuilding the session, memory, and observability layer yourself, which is the real lock-in cost, not a contractual one. **OpenAI's Agents SDK** has native tracing built for its own dashboard and is provider-adjacent by construction (it's built around OpenAI's Responses API), which is a soft lock-in: it works with other providers but the tracing and evaluation tooling is clearly built with OpenAI's own stack in mind. **CrewAI** is open source with low technical lock-in but real practical lock-in once a codebase is written against its `Process` model, because migrating off means re-expressing the workflow as a graph. **AutoGen** carries the sharpest lock-in risk of all: not vendor lock-in, but *time* lock-in — code written against it is written against a project in maintenance mode, and the debugging and community-support surface will only shrink from here. Debugging quality across all of them tracks directly with how much state is inspectable: LangGraph's `get_state()`/time-travel and ADK's managed session traces are strong; the OpenAI SDK's thin loop is easy to reason about precisely because there's less of it to debug; CrewAI and AutoGen's debugging stories both lag, with CrewAI's own limitation being that delegation-chain tracing in complex crews stays shallow.

### The numbers that actually discriminate

A handful of concrete, comparable figures worth having cold, with the caveat that framework benchmarking is workload-sensitive and none of these should be quoted as a universal ranking:

- Framework choice alone has been shown to move agent benchmark scores by **up to 30 percentage points** on the identical underlying model — evidence that the graph design and tool set dominate the framework brand, not the other way around.
- One comparative harness reported LangGraph at roughly **$0.08/task** on cost and latency, CrewAI winning time-to-a-working-prototype, and AutoGen winning open-ended reasoning quality at **5-6x the cost** of the cheaper options — a real Pareto tradeoff, not a strict win for any one framework.
- CrewAI has been measured carrying **up to 3x the token overhead** of LangGraph on simple workflows, which is the concrete cost of its higher-ceremony role/backstory prompting style.
- CrewAI reached an enterprise tier in **March 2026** with roughly **45,400 GitHub stars** at v1.10.1, evidence of real adoption, not just prototype popularity.
- Microsoft Agent Framework hit **GA 1.0 on 3 April 2026** for both Python and .NET; AutoGen and Semantic Kernel both went into maintenance mode as of that transition.

---

## Build it from scratch

There is no single lab here because the point of this module is comparative, not implementational — the labs live under the frameworks themselves (`T07-langgraph-core`'s and `T07-agent-loop-from-scratch`'s). The exercise that actually builds the judgment this module tests: take one realistic task (a three-tool research agent with one approval gate) and sketch its shape in three of these frameworks side by side — LangGraph, OpenAI's Agents SDK, and hand-rolled. Count lines of ceremony versus lines of actual logic in each. The hand-rolled version and the OpenAI SDK version will look similar in size; the LangGraph version will have more structure and a state schema; and the exercise is honest about which of the three is worth its overhead for *this specific task*, not which one is "better."

---

## How it's done in production

| Symptom | Cause | Fix |
|---|---|---|
| Team picked CrewAI, workflow now needs conditional branching a sequential/hierarchical crew can't express | Chose the framework for prototyping speed, didn't evaluate long-term shape | Either accept the ceiling and route the branch outside the crew (a thin dispatcher calling different crews), or migrate the branching portion to a graph-based framework |
| LangGraph streaming code breaks after a minor version bump | Wrote against a specific stream wire format without pinning `version=` | Pin `version="v2"` (or whichever is current) explicitly; treat the streaming surface as unstable across framework versions |
| New hire recommends AutoGen for a 2026 project | Learned from an older tutorial or blog post | AutoGen and Semantic Kernel are in maintenance mode; Microsoft's own guidance is to use Agent Framework, GA since April 2026 |
| ADK-based agent works great in dev, session state doesn't persist in prod | Used `InMemorySessionService`, which is explicitly dev-only | Switch to `VertexAiSessionService` backed by Agent Engine before shipping |
| OpenAI Agents SDK agent loses all state on a container restart mid-run | The SDK has no native cross-process checkpointing; `Sessions` cover in-run memory, not crash durability | Either accept short-lived runs only, or put the SDK's agent logic behind a durable orchestrator (Temporal) if runs need to survive a restart |
| Hand-rolled agent reinvents a worse, buggier version of checkpointing, HITL, and streaming over eighteen months | Task genuinely outgrew a simple loop but nobody re-evaluated the framework decision | Re-run the "which axis matters" exercise; if durability and HITL are now real requirements, that's the signal to adopt LangGraph or ADK rather than keep patching |
| Framework benchmark cited to justify a choice doesn't hold up once shipped | Benchmark measured a different workload shape (framework scores swing up to 30pp by task/tool design, not framework identity) | Benchmark your own representative task before committing, not a public leaderboard number |

---

## Tradeoffs & when NOT to use each

- **LangGraph is usually the wrong choice** for a simple `model → tool → model` loop (per `T07-langgraph-core`'s own framing) and for teams that can't absorb a breaking-ish migration every couple of quarters — three streaming formats and a relocated `create_agent` factory in fifteen months is a real tax, not a hypothetical one.
- **Google ADK is usually the wrong choice** outside a Google Cloud deployment. Its durability, session, and memory story is genuinely strong, and almost all of that strength is coupled to Vertex AI Agent Engine; take it off GCP and you're rebuilding the managed layer yourself, which erases the reason to pick it in the first place.
- **OpenAI's Agents SDK is usually the wrong choice** when you need durable execution across a crash, a multi-day approval gate, or model-provider neutrality as a hard requirement — it's the thinnest loop here, which is exactly why it doesn't give you those things for free.
- **CrewAI is usually the wrong choice** for any workflow with genuine conditional branching or a topology that isn't well-described as "sequential" or "one manager delegating to specialists." It is also a costly choice at scale given the measured token overhead versus LangGraph on equivalent simple workflows.
- **AutoGen is now usually the wrong choice, full stop, for new work.** This isn't a stylistic preference — the maintaining organization redirected its own roadmap to a different product. The only defensible reason to touch AutoGen in 2026 is maintaining an existing codebase already built on it, and even there the honest advice is to plan a migration to Agent Framework.
- **Hand-rolled is usually the wrong choice** the moment you need more than one of: durable resume across a crash, a real approval gate that survives a day, multi-format streaming to a UI, or a topology with branching and fan-out that would otherwise be reimplementing `T07-langgraph-core`'s reducer model badly. Below that bar, it is very often the *right* choice, and saying so plainly is the strongest signal in this whole module — `T07-agent-loop-from-scratch` and `T07-harness-engineering` both make the same point from different angles: every framework component encodes an assumption that expires, and assumptions you wrote yourself are at least assumptions you understand.

---

## Interview questions

### Q1 — Pick a framework for a three-tool research agent with no approval gate and no multi-agent need. Justify it.
**Testing:** whether you default to a name-brand framework out of habit.
**Answer:** Hand-rolled, or the thinnest available option (OpenAI's Agents SDK if you're already on that model provider). No durability requirement, no HITL requirement, no multi-agent requirement — every framework on this list is solving problems this task doesn't have, at the cost of ceremony this task doesn't need.
**Follow-up trap:** *"Wouldn't LangGraph future-proof you if requirements grow?"* — maybe, but that's a bet on a specific kind of growth, and `T07-harness-engineering`'s Bitter Lesson point applies: building for a future requirement you don't have yet is exactly the scaffolding tax that has to be deleted later if the guess is wrong. Start minimal, add structure when an eval or an incident shows you need it.

### Q2 — Why is AutoGen the wrong recommendation for a new 2026 project?
**Testing:** currency, not opinion.
**Answer:** Microsoft placed AutoGen and Semantic Kernel into maintenance mode and shipped Microsoft Agent Framework (public preview Oct 2025, GA 1.0 in April 2026) as the actual successor, merging AutoGen's multi-agent orchestration with Semantic Kernel's production features. Recommending AutoGen without naming this is citing stale information, the same way quoting a `recursion_limit` default of 25 is stale for LangGraph.
**Follow-up trap:** *"What if the team already has a large AutoGen codebase?"* — maintaining it is reasonable in the short term (bug fixes and security patches still flow), but the honest long-term answer is a migration plan to Agent Framework, not continued net-new investment in a frozen project.

### Q3 — When is Google ADK the right choice, and when is it a trap?
**Answer:** Right choice inside a Google Cloud shop that wants managed session/memory state, native bidirectional multimodal streaming, and multi-agent composition as a first-class primitive from day one. Trap outside that context: its durability and session story is real but tightly coupled to Vertex AI Agent Engine, and the local `InMemorySessionService` used in development is explicitly not production-suitable — teams that prototype against it and don't switch before shipping lose all session state on restart.
**Follow-up trap:** *"Is that lock-in a dealbreaker?"* — not automatically; if you're already committed to GCP, the coupling is a feature (you get a managed layer for free) rather than a cost. The dealbreaker case is a multi-cloud or cloud-agnostic requirement, where the coupling is real and the framework is the wrong fit regardless of its technical quality.

### Q4 — CrewAI prototypes fast and then a team hits a wall. What wall, specifically?
**Answer:** Its process model — sequential or hierarchical crews — doesn't express genuine conditional branching. A workflow that needs "if X, route to path A, else path B, then converge" doesn't map cleanly onto either process type, and teams either bolt on external dispatch logic around the crew or rewrite the branching portion as a graph. It also carries a measured token-overhead cost (up to 3x LangGraph's on equivalent simple workflows), which compounds at scale.
**Follow-up trap:** *"Is that a reason not to use CrewAI at all?"* — no, it's a reason to use it for what it's actually good at: role-based, mostly-linear workflows where the org-chart mental model maps onto the task, and where fast time-to-prototype matters more than long-term flexibility. Using it for a task with real branching from the start is the mistake, not using it at all.

### Q5 — Compare durability across LangGraph, ADK, and the OpenAI Agents SDK, concretely.
**Answer:** LangGraph checkpoints at every super-step by default with a checkpointer configured; resume replays from the last completed super-step. ADK's durability is Vertex AI Agent Engine's `SessionService` in production — real, but coupled to GCP deployment, and the dev-mode `InMemorySessionService` doesn't survive a restart. OpenAI's Agents SDK has no native cross-process checkpointing at all; `Sessions` give you conversational memory within a live run, not resumability after a crash — if you need that, you build it yourself or put the agent behind a durable orchestrator like Temporal.
**Follow-up trap:** *"Does that make the OpenAI SDK the worst choice for anything durable?"* — yes, stated plainly, and that's fine as long as it's a deliberate choice: the SDK is designed to be thin, and thin means you own durability. Picking it for a multi-day approval workflow without a durability plan is the mistake, not the SDK itself.

### Q6 — What's the actual evidence that framework choice matters less than people think?
**Testing:** whether you can argue against your own thesis honestly.
**Answer:** Framework choice alone has been shown to swing agent benchmark scores by up to 30 percentage points on the *identical* underlying model, which sounds like it proves framework matters enormously — but the honest reading is closer to the opposite: that swing is dominated by the graph design and tool set built inside the framework, not the framework's brand name. A bad LangGraph implementation loses to a good hand-rolled loop. This is the same conclusion `T07-harness-engineering` reaches from a different angle: harness-only changes (not model swaps) moved a coding agent from rank 30 to top 5 on Terminal Bench 2.0.
**Follow-up trap:** *"So does the framework matter at all, then?"* — yes, on the axes that are genuinely hard to build yourself well: durability, HITL, multi-format streaming, per-node retry policy. It doesn't matter much on raw task accuracy, which is a function of your tool design and prompt engineering regardless of which framework hosts them.

### Q7 — Your team wants multi-agent delegation. Which framework, and why not the others?
**Answer:** ADK or CrewAI, because both treat multi-agent composition as the core abstraction rather than something bolted onto a single-agent primitive — ADK via composable agent trees, CrewAI via role-based crews. AutoGen's conversational turn-taking model is also multi-agent-first but is a frozen codebase now. LangGraph and the OpenAI SDK both support multi-agent (subgraphs/`Send`, and `handoffs` respectively) but as composition on top of single-agent building blocks, which costs slightly more setup for pure delegation workflows but avoids paying a multi-agent abstraction tax for tasks that turn out not to need it.
**Follow-up trap:** *"Isn't 'multi-agent as core abstraction' strictly better if you know you need it?"* — only if you're confident you need it now and won't need to collapse back to a single agent later. `T07-agent-loop-from-scratch`'s own guidance is that a single agent with good tools beats a poorly-decomposed multi-agent system almost always, so a framework that makes multi-agent the default can bias a team toward premature decomposition.

### Q8 — Name one hard number that would make you switch off your current framework.
**Testing:** whether the evaluation is metric-driven or vibes-driven.
**Answer:** A concrete one: if a durability-free framework (OpenAI SDK, CrewAI, AutoGen) is running tasks at a per-step reliability where `T07-agent-loop-from-scratch`'s arithmetic bites — say 85% per-step success on a genuinely 8-10 step task, meaning roughly 20% of runs complete without a crash — and production incident data shows runs are dying mid-task with no resumability, that's the number that forces a move to LangGraph or ADK. The switch is justified by measured completion-rate loss, not by a framework's marketing.
**Follow-up trap:** *"What if the number doesn't clearly justify it, but the team just prefers a different framework?"* — that's a legitimate but different conversation (developer velocity, hiring pool, existing expertise), and it should be named as such rather than dressed up as a technical requirement. Conflating preference with necessity is how teams end up defending a bad decision with invented justifications.

### Q9 — Is "the model got smarter" ever a reason a framework choice ages badly?
**Answer:** Yes, and it's the exact mechanism `T07-harness-engineering`'s Bitter Lesson section names: heavier frameworks that encode more assumptions about what the model can't do age worse as the model improves, because those assumptions expire. A framework like ADK or CrewAI with a fixed multi-agent topology built for a 2024-era model may be actively worse than a 2026 model given fewer tools and a shorter loop. This isn't unique to any one framework on this list — it's sharper the more structure a framework imposes.
**Follow-up trap:** *"Does that mean hand-rolled ages best?"* — it ages differently, not automatically best: a hand-rolled loop has fewer baked-in assumptions to expire, but it also has none of the durability or HITL infrastructure that a growing task genuinely needs, so you trade "assumptions that expire" for "infrastructure you have to keep building yourself." Neither is a free lunch.

### Q10 — You inherit a codebase on AutoGen. What do you actually do?
**Testing:** practical migration judgment, not just "know it's deprecated."
**Answer:** Don't rip it out immediately — maintenance mode still means bug fixes and security patches flow, so a working system isn't on fire. Do stop new feature development against AutoGen's APIs, evaluate Microsoft Agent Framework's migration path (it's explicitly designed to absorb both AutoGen and Semantic Kernel projects), and prioritize the migration by how much the codebase leans on AutoGen-specific conversational-turn-taking patterns that don't map cleanly onto Agent Framework's model — that mapping work is the real migration cost, not a rename.
**Follow-up trap:** *"What if leadership says there's no budget for a migration right now?"* — then say plainly that the risk being accepted is a shrinking community, no new features, and a widening gap to whatever Agent Framework ships next, and get that risk acknowledgment in writing rather than silently absorbing it as a personal debugging burden later.

---

## Red flags that fail you

- Recommending AutoGen for new work without naming Microsoft Agent Framework.
- Treating "framework popularity" or GitHub stars as a proxy for fit to your specific workload.
- Claiming one framework is universally best rather than naming the axis it wins and the axis it loses.
- Not knowing that Google ADK's production durability story is coupled to Vertex AI Agent Engine.
- Assuming the OpenAI Agents SDK has native cross-process checkpointing because it has "Sessions."
- Reaching for CrewAI or ADK's multi-agent primitives before establishing a single agent is insufficient.
- No answer for when hand-rolled is the right choice.
- Citing a benchmark leaderboard number as if it transfers to your specific tool set and task shape.

## Cheat card

```
AXES AND WINNERS (know the axis, not a single "best")
  loop control:      LangGraph (explicit graph) > OpenAI SDK (thin, you own it)
  durability:        LangGraph (Pregel checkpoints) ≈ ADK (Vertex AI Agent Engine,
                      but GCP-coupled) >> OpenAI SDK (none native) > CrewAI/AutoGen
  streaming:         ADK (native Bidi multimodal) / LangGraph (7 modes, 3 formats
                      in 15mo — churn risk) > OpenAI SDK (native, stable) >
                      CrewAI/AutoGen (partial)
  HITL:              LangGraph interrupt()+resume (most composable) > ADK (session-
                      based pause, GCP-coupled) > OpenAI SDK guardrails (fail-fast,
                      not durable pause) > CrewAI/AutoGen (limited)
  multi-agent:       ADK / CrewAI (core abstraction, tree/crew) ≈ AutoGen (conv.
                      turn-taking, FROZEN) > LangGraph/OpenAI SDK (composed on top:
                      subgraphs+Send / handoffs — no tax if you don't need it)
  lock-in:           LangGraph (OSS, low) ≈ CrewAI (OSS, but process-model lock-in)
                      < OpenAI SDK (provider-adjacent) < ADK (GCP-coupled, HIGH)
                      AutoGen: not vendor lock-in, TIME lock-in (frozen project)
  debugging:         tracks inspectable state: LangGraph get_state()/time-travel,
                      ADK managed traces > OpenAI SDK (thin=easy) > CrewAI/AutoGen

AUTOGEN: Microsoft maintenance mode (2025) -> Microsoft Agent Framework
  GA 1.0 2026-04-03 (Python+.NET), merges AutoGen + Semantic Kernel
  DO NOT recommend AutoGen for new 2026 work

NUMBERS
  framework choice alone: up to 30pp benchmark swing on IDENTICAL model
    (means: graph/tool design dominates, not framework brand)
  LangGraph ~$0.08/task cost/latency in one comparative harness
  AutoGen: 5-6x the cost of cheaper options for open-ended reasoning wins
  CrewAI: up to 3x LangGraph's token overhead on simple workflows
  CrewAI: enterprise tier Mar 2026, ~45,400 GitHub stars @ v1.10.1
  0.85^10 ≈ 20% completion — the arithmetic that makes durability matter

WRONG CHOICE, BY FRAMEWORK
  LangGraph:    simple model->tool->model loop; can't absorb migration cadence
  ADK:          outside Google Cloud deployment
  OpenAI SDK:   need durable resume across a crash, or provider neutrality
  CrewAI:       genuine conditional branching, not sequential/hierarchical
  AutoGen:      any NEW project in 2026 (maintenance mode)
  Hand-rolled:  need durable resume + real HITL + multi-format streaming
                + branching/fan-out all at once (that's LangGraph/ADK territory)

DEFAULT BET IF UNSURE: start hand-rolled or thinnest SDK, add structure
  only when an eval or incident PROVES you need durability/HITL/multi-agent
```

## Sources

- [Agent Development Kit (ADK) — Technical Overview](https://google.github.io/adk-docs/get-started/about/) — ADK's agent-orchestration-first design, Sequential/Parallel/Loop agents; accessed 2026-08-01
- [Part 1. Intro to streaming — Agent Development Kit (ADK)](https://google.github.io/adk-docs/streaming/dev-guide/part1/) — Bidi-streaming, multimodal production framework; accessed 2026-08-01
- [Manage sessions with Agent Development Kit — Google Cloud](https://cloud.google.com/agent-builder/agent-engine/sessions/manage-sessions-adk) — `InMemorySessionService` vs `VertexAiSessionService`; accessed 2026-08-01
- [OpenAI Agents SDK](https://openai.github.io/openai-agents-python/) — Agent/Runner/Tools/Handoffs/Guardrails/Sessions primitives, tracing, guardrail fail-fast mechanics; accessed 2026-08-01
- [Handoffs — OpenAI Agents SDK](https://openai.github.io/openai-agents-python/handoffs/) — handoff scoping to a single run, guardrail application to first/last agent; accessed 2026-08-01
- [Microsoft Agent Framework Overview — Microsoft Learn](https://learn.microsoft.com/en-us/agent-framework/overview/) — successor framework, merges AutoGen + Semantic Kernel; accessed 2026-08-01
- [Microsoft Ships Production-Ready Agent Framework 1.0 for .NET and Python](https://visualstudiomagazine.com/articles/2026/04/06/microsoft-ships-production-ready-agent-framework-1-0-for-net-and-python.aspx) — GA date 2026-04-03; accessed 2026-08-01
- [CrewAI vs AutoGen 2026: Honest Comparison](https://cordum.io/blog/crewai-vs-autogen-2026) — process model rigidity, token overhead, GitHub stars, enterprise tier date; accessed 2026-08-01
- [2026 AI Agent Framework Showdown — QubitTool](https://qubittool.com/blog/ai-agent-framework-comparison-2026) — comparative cost/latency/reasoning-quality figures across frameworks; accessed 2026-08-01
- `curriculum/07-agentic-ai/06-langgraph-core.md` (`T07-langgraph-core`) — LangGraph mechanics, streaming format history, migration cadence this module summarizes
- `curriculum/07-agentic-ai/25-harness-engineering.md` (`T07-harness-engineering`) — Bitter Lesson framing, harness-vs-model evidence cited in the lineage
- `curriculum/07-agentic-ai/01-agent-loop-from-scratch.md` (`T07-agent-loop-from-scratch`) — reliability arithmetic, single-agent-vs-multi-agent default guidance

## Changelog
- 2026-08-01 — created
