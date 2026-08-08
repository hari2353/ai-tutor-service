# A2A Protocol: Agent Cards, Task Lifecycle, vs MCP

> **Track:** T07 Agentic AI · **Time:** 1.5h · **Prereqs:** none · **Updated:** 2026-08-01
> **Module id:** `T07-a2a-protocol` · **Tags:** protocol

## The 30-second version

A2A is a peer-to-peer protocol for agents built by different teams, on different frameworks, run by different organizations, to discover each other and delegate work without either side seeing the other's internals. Discovery is a JSON **Agent Card** — a capability manifest an agent publishes at a well-known path — and delegated work is a **Task**, a stateful object that moves through an eight-state lifecycle (`submitted` → `working` → ... → a terminal state), streamable over SSE and reachable later via polling or a push-notification webhook if the caller disconnects. It reached **v1.0 in 2026** under Linux Foundation governance, and as of mid-2026 it has broad organizational backing — 150+ companies including Microsoft, AWS, Salesforce, SAP — but genuinely thin production usage; most real deployments are still proofs of concept, and that gap between backing and production reality is the honest thing to say about it. The precise relationship to MCP is not competition: MCP connects one agent to its tools and context; A2A connects agents to each other as peers with their own task state. An orchestrator built with LangGraph might use A2A to hand a sub-task to a specialist agent it doesn't control, and that specialist might turn around and use MCP to reach its own database.

## Why this gets asked

Because "multi-agent" shows up on every 2026 job description, and A2A is the one open standard that specifically targets the *cross-boundary* case LangGraph, CrewAI, and every in-process framework don't solve: agent A and agent B are not in the same process, don't share a state schema, and may not even trust each other. The interviewer wants to know if you can draw that boundary precisely, or if "multi-agent" is a single blurry concept to you. The failure they've likely seen personally is a team building an in-process multi-agent system and calling it "A2A" because they read the acronym in a blog post, or the opposite: reaching for A2A's task machinery to coordinate two agents that live in the same LangGraph graph, where a `Send` and a shared channel would have been ten lines instead of a protocol.

---

## Lineage: past → present → future

**What came before.** Before A2A, cross-organization agent communication meant one of three things, each with a specific failure: a bespoke REST API per integration (works, but is an N×M integration problem the moment a third agent joins); wrapping the other agent as an MCP "tool" (loses task state, streaming updates, and any notion of the other side being a peer rather than a subordinate function); or nothing at all — most "multi-agent systems" through 2024 were multiple LLM calls inside one process, sharing one framework's state, which isn't cross-boundary coordination at all, just decomposition. Google published A2A in April 2025 specifically to give agents from different vendors a common task-delegation contract, the same "N×M becomes N+M" argument MCP made a year earlier for tools, applied one layer up to agents themselves.

**Where it stands now.** A2A moved to Linux Foundation governance in June 2025 and reached **v1.0 in early 2026**, with a **v1.0.1 extension mechanism** (May 2026) letting the core spec grow new RPC methods and state machines without breaking the base protocol. The backing is real and broad: reported figures put support at **150+ organizations** including Google, Microsoft, AWS, Salesforce, SAP, ServiceNow, Workday, and IBM ([Linux Foundation figures via Tyk, accessed 2026-08-01](https://tyk.io/learning-center/a2a-protocol-architecture-and-technical-specification/)). The honest caveat, stated by multiple independent 2026 analyses, is that **production usage lags badly behind that backing** — most A2A implementations in the wild are still proofs of concept, and cross-vendor production systems using A2A for real inter-company delegation remain uncommon. This is a normal standards-adoption curve (logo support arrives before integration work does), but say the gap out loud rather than implying A2A is already how agents talk to each other in production. MCP, by contrast, has the adoption numbers to back the hype (see `T07-mcp-deep-dive`); A2A does not yet.

**Where it's heading.** Medium confidence: A2A and MCP converge into a standard combination rather than staying separate concerns candidates need to justify choosing between — an orchestrating agent uses A2A outward to delegate to peers and MCP inward to reach its own tools, and frameworks (LangGraph, the Microsoft Agent Framework, Google ADK) are already shipping native support for both side by side. Lower confidence: whether A2A's task lifecycle becomes the substrate for cross-organization human-in-the-loop approval (a task sitting in `input-required` for days while a human at another company reviews it) — the state machine supports it, but almost no one has built and load-tested that flow yet. Speculative: whether A2A sees genuine adoption outside large-vendor ecosystems, where the coordination problem it solves — different teams, different frameworks, mutual distrust — is real, versus inside a single company's stack, where a shared framework's native primitives (LangGraph's `Send`, a supervisor pattern — see `T07-multi-agent-topologies`) are simpler and already sufficient. Treat vendor commitment to A2A as a leading indicator of interest, not proof of production value.

---

## Mental model

```
   AGENT A (orchestrator, LangGraph, company X)          AGENT B (specialist, company Y)
        │                                                       │
        │  1. GET https://agent-b.example.com/.well-known/      │
        │     agent-card.json  ────────────────────────────────▶│
        │  ◀── AgentCard{skills, transports, securitySchemes} ──┤
        │                                                       │
        │  2. SendStreamingMessage(task) ──────────────────────▶│
        │  ◀── SSE: TaskStatusUpdateEvent{state: "working"} ────┤
        │  ◀── SSE: TaskArtifactUpdateEvent{chunk 1/3} ─────────┤
        │  ◀── SSE: TaskArtifactUpdateEvent{chunk 2/3} ─────────┤
        │  ◀── SSE: TaskStatusUpdateEvent{state: "completed"} ──┤
        │                                                       │
        │  (if A disconnects mid-task: webhook push, or         │
        │   GetTask polling, picks the result up later)         │
```

The one sentence to internalise: **an Agent Card is a menu, a Task is an order with a receipt you can check on**. MCP has nothing like the second half — a tool call is a single request/response, not a stateful, resumable, streamable unit of work owned by the other side.

---

## How it actually works

### 1. The Agent Card — discovery and capability advertisement

Any A2A server publishes a JSON document at a well-known path — commonly `/.well-known/agent-card.json` in current spec material, though this exact filename has moved before (`agent.json` in earlier drafts) and is worth re-verifying against the spec version you're integrating against. The card declares:

```json
{
  "name": "invoice-reconciliation-agent",
  "description": "Matches vendor invoices against PO records and flags discrepancies.",
  "url": "https://agents.example.com/a2a",
  "version": "1.2.0",
  "capabilities": {"streaming": true, "pushNotifications": true, "extendedAgentCard": true},
  "skills": [
    {"id": "reconcile-invoice", "description": "Given an invoice id, reconcile against POs.",
     "inputModes": ["application/json"], "outputModes": ["application/json", "text/plain"]}
  ],
  "securitySchemes": {"oauth2": {"type": "oauth2", "flows": {"authorizationCode": {"..."}}}},
  "security": [{"oauth2": ["invoice:read"]}]
}
```

A client fetches this **without authentication** first — the card itself is public metadata — then picks a `skill`, checks `securitySchemes` to know what auth flow to run, and only then sends work. Capability discovery this way is the direct analog of `tools/list` in MCP, but one layer up: instead of listing callable functions, it lists *what kind of agent this is and how to engage it*.

**Extended agent cards.** An agent can advertise `capabilities.extendedAgentCard: true` in its public card, then require authentication to fetch a fuller card via `GetExtendedAgentCard` — a way to keep advanced or higher-trust capabilities out of the fully public listing.

### 2. The task lifecycle — the part that has no MCP equivalent

A `Task` carries a state machine, not a fire-and-forget call:

| State | Meaning |
|---|---|
| `submitted` | Accepted, not yet started |
| `working` | Actively being processed |
| `input-required` | Paused; the agent needs more information from the caller |
| `auth-required` | Paused; the agent needs the caller to complete an auth step |
| `completed` | Finished successfully — terminal |
| `failed` | Finished with an error — terminal |
| `canceled` | Stopped before completion — terminal |
| `rejected` | The agent declined to perform the task — terminal |

Five states are effectively an outer loop around the same problem `T07-agent-loop-from-scratch` solves for a single agent: `input-required` is a durable pause point, exactly like an `interrupt()` in LangGraph (`T07-langgraph-durable`), except the "human" on the other end of the pause might be a different company's agent, hours or days away from responding. This is why A2A tasks are addressed by a persistent `taskId` and `contextId` rather than living only in one process's memory — they have to survive exactly the kind of gap a checkpointer is built for, just across an organizational boundary instead of a process restart.

### 3. Messages, Parts, and Artifacts

- **Message** — one turn of communication, tagged with a `role` (`user` or `agent`), made of one or more **Parts**.
- **Part** — the actual content unit: `TextPart` (plain text), `FilePart` (inline bytes or a URL reference), `DataPart` (structured JSON). This three-way split is deliberate: a task result that's "some text plus a generated PDF plus a structured summary object" is naturally three parts, not one blob with an ad hoc content-type sniff.
- **Artifact** — the tangible output of a task (a document, a dataset, a report), itself composed of Parts, and streamable incrementally with `append`/`lastChunk` chunking hints so a large artifact doesn't have to arrive in one message.

### 4. Streaming and disconnected delivery

`SendStreamingMessage` opens an SSE connection; the caller receives a sequence of `TaskStatusUpdateEvent` (lifecycle transitions, intermediate messages) and `TaskArtifactUpdateEvent` (chunked artifact delivery) until the task reaches a terminal or interrupted state. For long-running or unreliable-connection scenarios, A2A also supports **push notifications**: the caller registers a webhook, and the server calls it — typically on a significant state change like a terminal state, `input-required`, or `auth-required` — with the same payload shape streaming would have delivered. If neither streaming nor a webhook fired in time, the caller can always fall back to polling `GetTask`. This three-way redundancy (stream, push, poll) is the practical answer to "what if the caller's connection dies mid-task," a failure mode a plain synchronous request/response protocol has no good answer for.

### 5. What A2A solves that MCP doesn't

MCP's contract is client-to-server: a host application connects a model to a server that exposes tools/resources/prompts it controls. There is no notion in MCP of the "server" being another autonomous agent with its own goals, its own task state that outlives the connection, or its own reason to say "not right now, I need more input" — a tool call either returns or errors. A2A's entire task lifecycle, artifact model, and Agent Card discovery exist because peer-to-peer agent delegation needs: **(a)** a way to describe *what kind of agent* you're talking to before committing to a conversation shape (the Agent Card), **(b)** a way to represent work that outlives one HTTP request (the Task), and **(c)** a way to resume that work regardless of which side went offline first (polling + push notifications). None of that is meaningful for "call this tool and get a JSON blob back," which is exactly MCP's job and exactly why MCP doesn't have it.

### 6. Auth and identity across an agent boundary

A2A layers its security model on standard web auth rather than inventing a new one: OAuth 2.1 authorization code flow with JWT validation is the documented baseline, and Agent Cards themselves can be **JWT-signed** to prevent a malicious actor from publishing a spoofed card claiming to be a trusted agent. Because the card declares its own `securitySchemes` up front, a client can inspect what's required *before* attempting to engage, and adapt its auth flow per agent rather than assuming one scheme fits every peer it talks to. The identity question this raises and doesn't fully answer yet: when Agent A acts on a task delegated by Agent B, which is itself acting on behalf of human user U, what identity does the downstream system see — A, B, or U? This is the same confused-deputy shape covered in `T07-mcp-deep-dive`, one layer up the chain, and it is not yet a solved, standardized part of the spec; treat any claim that A2A "solves" delegated identity as premature.

---

## Build it from scratch

The whole protocol is a card, a task store, and two JSON-RPC methods. Everything else is convenience. Roughly 80 lines gets you something a real A2A client can talk to, and building it is what makes the "is this actually A2A or just two agents chatting" question easy to answer.

```python
# untested sketch — illustrates the shape, not a spec-conformant implementation.
# Verify method names and the card path against the spec revision you target.
import uuid
from typing import Any, Literal

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

# ---- 1. The Agent Card: discovery. Static JSON at a well-known path. ----
CARD = {
    "name": "invoice-reconciliation-agent",
    "description": "Matches vendor invoices against PO records.",
    "url": "https://agents.example.com/a2a",
    "version": "1.2.0",
    "capabilities": {"streaming": True, "pushNotifications": False},
    "securitySchemes": {"oauth2": {"type": "oauth2"}},
    "skills": [{"id": "reconcile", "description": "Reconcile an invoice against a PO"}],
}

@app.get("/.well-known/agent-card.json")
def agent_card() -> dict:
    return CARD


# ---- 2. The task store. This is what makes a Task outlive one HTTP request. ----
# In-memory here; in production this is Postgres or Redis, because a task sitting
# in `input-required` for three days must survive your own service restarting.
TaskState = Literal["submitted", "working", "input-required", "completed", "failed", "canceled"]

class Task(BaseModel):
    id: str
    contextId: str
    state: TaskState = "submitted"
    artifacts: list[dict[str, Any]] = []

TASKS: dict[str, Task] = {}


# ---- 3. JSON-RPC 2.0 dispatch. Two methods carry the core of the protocol. ----
class RpcRequest(BaseModel):
    jsonrpc: Literal["2.0"]
    id: str | int
    method: str
    params: dict[str, Any] = {}

@app.post("/a2a")
def rpc(req: RpcRequest) -> dict:
    if req.method == "message/send":
        # a new task, or a follow-up turn on an existing contextId
        ctx = req.params.get("contextId") or str(uuid.uuid4())
        task = Task(id=str(uuid.uuid4()), contextId=ctx, state="working")
        TASKS[task.id] = task
        result = do_work(task, req.params["message"])   # your agent runs here
        return {"jsonrpc": "2.0", "id": req.id, "result": result.model_dump()}

    if req.method == "tasks/get":
        # the poll path: how a caller recovers after its connection died
        task = TASKS.get(req.params["id"])
        if task is None:
            return {"jsonrpc": "2.0", "id": req.id,
                    "error": {"code": -32001, "message": "Task not found"}}
        return {"jsonrpc": "2.0", "id": req.id, "result": task.model_dump()}

    return {"jsonrpc": "2.0", "id": req.id,
            "error": {"code": -32601, "message": "Method not found"}}


def do_work(task: Task, message: dict[str, Any]) -> Task:
    """Terminal or interrupted state, never a bare return. The state machine is
    the contract: a caller decides what to do next by reading `state`, so an
    agent that always returns `completed` has thrown away the protocol."""
    if needs_human_approval(message):
        task.state = "input-required"      # caller must send another message/send
        return task
    task.artifacts = [{"name": "reconciliation", "parts": [{"kind": "text", "text": "..."}]}]
    task.state = "completed"
    return task
```

**The client side is three steps:** `GET` the card, pick a skill and satisfy the `securitySchemes` it declares, then `POST` a `message/send`. On a dropped connection, `tasks/get` with the stored `taskId` recovers the state, which is the whole reason the Task exists as a first-class object rather than a response body.

**Do this to make the design click:** implement `do_work` so it returns `input-required` on the first call and `completed` only after a second message on the same `contextId`. That single change forces you to persist state between requests, and it is the exact point where a plain request/response tool call stops being sufficient and A2A starts earning its complexity. If your implementation never returns a non-terminal state, you have built an HTTP API with extra JSON, not an A2A agent.

---

## How it's done in production

| What production adds | Why it matters |
|---|---|
| **Framework-native A2A support** | Google ADK, the Microsoft Agent Framework, and LangGraph-adjacent tooling ship A2A client/server helpers so you're not hand-rolling JSON-RPC and SSE parsing |
| **Agent registries / marketplaces** | An organization-internal or cross-org directory of Agent Cards, so discovery isn't "someone emails you a URL" |
| **Webhook infrastructure for push notifications** | Real delivery guarantees (retry, dedup, signature verification on the webhook payload) that the spec describes but doesn't provide for you |
| **Task store** | Persisting `taskId`/`contextId` state so a task in `input-required` for three days survives a restart of your own service, mirroring what a LangGraph checkpointer does inside one process (`T07-langgraph-durable`) |

**What breaks at scale**

| Symptom | Cause | Fix |
|---|---|---|
| Two teams both call it "A2A" but nothing interoperates | One side actually built an in-process multi-agent system and used the term loosely | Verify against the actual spec: Agent Card at the well-known path, JSON-RPC/gRPC/REST bindings, real task states — not just "two LLM calls talking to each other" |
| A long-running task silently vanishes after the caller's process restarts | No task store; state only lived in the caller's memory | Persist `taskId`/`contextId` server-side; poll `GetTask` on reconnect rather than assuming the stream picks up where it left off |
| A task sits in `input-required` forever | No monitoring on non-terminal states; nobody is watching for tasks stuck outside the five terminal/working states | Alert on tasks older than an SLA threshold still in `input-required`/`auth-required`; treat it like a stale approval gate (`T07-langgraph-durable` Q12's stale-approval problem, one org apart) |
| A spoofed Agent Card gets a client to send real work to an attacker's endpoint | Card fetched over an unauthenticated GET with no integrity check | Verify JWT-signed cards where the ecosystem supports it; pin known-good agent URLs rather than resolving cards from arbitrary discovery |
| Cross-org auth breaks the first time a real second company integrates | Auth flow was only ever tested against one authorization server, assumptions baked in | Test against the `securitySchemes` the *other* agent's card actually declares, not the one you assumed; don't hardcode one OAuth provider |

---

## Tradeoffs & when NOT to use it

- **Don't reach for A2A to coordinate two agents inside one process or one framework.** If both agents live in the same LangGraph graph, a `Send` and a shared, reducer-backed channel (`T07-langgraph-core`) is simpler, faster, and doesn't need HTTP, SSE, or a task store — A2A's entire value proposition is the *cross-boundary* case, and paying its protocol cost inside a boundary that doesn't exist is pure overhead.
- **Don't adopt it purely because it's on the job description.** As of mid-2026 the honest assessment is broad organizational backing and thin production usage; most teams integrating a genuine external agent today are still likely to reach for a bespoke authenticated REST API, and that's a reasonable call, not a failure to keep up. Say this plainly rather than implying A2A adoption is further along than it is.
- **Don't use A2A's task machinery for something that isn't actually long-running or delegatable.** If the "other agent" always responds synchronously in under a second and never needs `input-required`, you've adopted a state machine, a webhook contract, and a JSON-RPC/SSE surface for what a single HTTP call would do.
- **The identity-across-a-boundary problem is not fully solved.** If your use case genuinely requires knowing whose authority a multi-hop delegated task is acting under at every step, treat that as an open design problem you have to solve yourself today, not something A2A hands you.

---

## Interview questions

### Q1 — What problem does A2A solve that MCP doesn't?
**Testing:** whether you can state the boundary precisely instead of treating both as "agent protocols."
**Answer:** MCP connects one agent to the tools and context it needs — client-to-server, resource-shaped. A2A connects independent agents to each other as peers, built by different teams on different frameworks, with a capability-discovery step (the Agent Card) and a stateful, resumable unit of delegated work (the Task) that a single tool call has no equivalent of.
**Follow-up trap:** *"So could MCP do this if you just modeled the other agent as a tool?"* — you could, but you'd lose task state that outlives the request, streaming status/artifact updates, push-notification recovery if the caller disconnects, and Agent-Card-based discovery of what the other side can even do before you commit to talking to it.

### Q2 — What's in an Agent Card, and where does a client find one?
**Answer:** A JSON document — name, description, `skills`, supported input/output modes, `securitySchemes`, and capability flags like `streaming` and `pushNotifications` — published at a well-known path (commonly `/.well-known/agent-card.json`, though verify the exact filename against your spec version). Fetched unauthenticated first, so a client can decide what auth flow to run before engaging.
**Follow-up trap:** *"What stops someone from publishing a fake card claiming to be a trusted agent?"* — JWT-signed Agent Cards address integrity, but only where both sides support it; otherwise you're trusting DNS and TLS for the domain the card was fetched from, same as trusting any web resource, which is why pinning known-good agent URLs matters more than trusting open discovery.

### Q3 — Walk me through the task lifecycle.
**Answer:** Eight states: `submitted`, `working`, `input-required`, `auth-required` (non-terminal, pauses for more information or an auth step), and four terminal states — `completed`, `failed`, `canceled`, `rejected`. A task is addressed by a persistent `taskId`/`contextId`, not tied to one HTTP connection.
**Follow-up trap:** *"How is `input-required` different from just returning an error asking for more info?"* — it's a durable pause, not a failure: the task keeps its identity and context, and the caller can resume it later by sending the missing information against the same `taskId`, exactly like an `interrupt()` in a durable LangGraph run (`T07-langgraph-durable`) rather than starting over.

### Q4 — Design the delivery mechanism for a task that takes six hours.
**Answer:** Three complementary paths, not one. Streaming (`SendStreamingMessage`, SSE) for a caller that stays connected. Push notifications via a registered webhook for a caller that won't — fired on significant state changes like reaching a terminal state or `input-required`. `GetTask` polling as the universal fallback if both of the above missed a beat. Don't rely on only one; connections drop and webhooks get missed.
**Follow-up trap:** *"Your webhook fires twice for the same state transition. What do you do?"* — dedup on `taskId` plus the state/sequence in the payload; the spec doesn't guarantee exactly-once delivery, so treat webhook handling like any other at-least-once system and make the handler idempotent.

### Q5 — What are Parts and Artifacts, and why three Part types instead of one generic blob?
**Answer:** A Message or Artifact is composed of one or more Parts: `TextPart` for plain text, `FilePart` for binary (inline or URL-referenced), `DataPart` for structured JSON. Splitting by type lets a single task result carry, say, a human-readable summary, a generated PDF, and a structured object as three typed, independently processable pieces instead of one blob a client has to sniff and parse.
**Follow-up trap:** *"How do large artifacts avoid a single giant payload?"* — chunked delivery via `append`/`lastChunk` hints on `TaskArtifactUpdateEvent`, so a large document streams incrementally rather than arriving as one multi-megabyte message.

### Q6 — Is A2A actually used in production in 2026?
**Testing:** whether you'll recite marketing or give an honest read.
**Answer:** Backing is broad — 150+ organizations including major cloud and enterprise vendors — and it reached v1.0 in early 2026 under Linux Foundation governance. But multiple independent 2026 analyses describe most real-world A2A implementations as proofs of concept; production cross-vendor delegation is still uncommon. That's a normal standards curve (logos arrive before integration work), and it's the honest thing to say rather than implying it's already how agents talk to each other in the field.
**Follow-up trap:** *"Then why would you build on it today?"* — if your actual problem is cross-organization agent delegation with a real need for discovery and durable task state, A2A gives you a standard instead of a bespoke contract per partner — worth it even at low current adoption, because the alternative is inventing the same task-lifecycle machinery yourself. If your problem is two agents in your own stack, don't.

### Q7 — Your task sits in `input-required` for three days. What do you build around that?
**Answer:** A monitor that alerts on non-terminal tasks older than an SLA threshold, because nothing in the protocol itself will tell you a task is stuck — it's just sitting there, structurally correct, waiting. Persist the task state server-side so a restart of your own service doesn't lose track of it, and treat the eventual resume the same way you'd treat a stale approval in a durable agent loop.
**Follow-up trap:** *"The human approves after the underlying data changed. What happens?"* — the same stale-approval problem covered for LangGraph HITL in `T07-langgraph-durable` Q12, one organizational hop removed: re-validate preconditions before acting on the resumed task, or attach an explicit expiry, rather than blindly executing against data that's now three days stale.

### Q8 — Auth and identity: Agent A delegates a task to Agent B on behalf of user U. What identity does the downstream system see?
**Testing:** whether you'll claim this is solved when it isn't.
**Answer:** A2A's baseline is OAuth 2.1 with JWT validation and JWT-signed Agent Cards, which secures the A-to-B hop itself. What identity flows *through* that hop — A's, B's, or U's — is not a fully standardized part of the spec as of 2026; it's the same confused-deputy shape as MCP's token-passthrough problem, one layer up, and treating it as solved is a mistake. Design your own token-exchange or delegation-claim pattern rather than assuming the protocol hands you one.
**Follow-up trap:** *"How would you fix it yourself?"* — carry an explicit delegation claim (who authorized this, on whose behalf, with what scope) as structured data in the task, verified at each hop, rather than relying on whichever agent's credential happens to be attached to the outbound call — the A2A analog of validating token audience in MCP.

### Q9 — Compare A2A's Task to a LangGraph checkpoint conceptually.
**Answer:** Both exist to let work survive past the point where the initiating connection can no longer be assumed alive. A LangGraph checkpoint persists a single process's state across a super-step boundary so a failed run resumes instead of restarting (`T07-langgraph-durable`). An A2A Task persists delegated work across an *organizational* boundary — different company, different process, potentially different framework entirely — with `taskId`/`contextId` playing the role `thread_id` plays for a checkpointer, and `input-required` playing the role `interrupt()` plays.
**Follow-up trap:** *"So could you back an A2A task with a LangGraph checkpointer?"* — yes, and that's a natural pairing: the specialist agent receiving the A2A task can be a LangGraph graph internally, using its own checkpointer for durability, while A2A handles the outward-facing discovery and task-state contract with the caller. The two operate at different layers and compose cleanly.

### Q10 — When would you explicitly choose not to use A2A?
**Testing:** the senior "when NOT to" signal.
**Answer:** Inside a single process or framework boundary — use the framework's native multi-agent primitives (`T07-multi-agent-topologies`) instead, since A2A's discovery and task-lifecycle machinery solves a cross-boundary problem you don't have. Also skip it for synchronous, sub-second interactions that never need `input-required` or streaming — that's a plain authenticated API call, and adopting A2A's SSE/webhook/task-store surface for it is pure overhead.
**Follow-up trap:** *"Your team already has a REST integration with a partner's agent and it works fine. Do you migrate to A2A?"* — not unless a third party is about to join, or you specifically need discovery, streaming task updates, or durable pause-and-resume that your bespoke API doesn't have. Migrating a working integration to a newer standard purely for the label is the same anti-pattern as adopting LangGraph for a three-step pipeline.

---

## Red flags that fail you

- Calling any in-process multi-agent setup "A2A" without an Agent Card, real task states, or the standard bindings.
- Claiming A2A has meaningfully high production adoption in 2026 without the caveat that most implementations are still proofs of concept.
- Not knowing the difference between a Task's non-terminal states (`working`, `input-required`, `auth-required`) and its terminal ones (`completed`, `failed`, `canceled`, `rejected`).
- Treating A2A and MCP as competing choices rather than composable layers.
- Claiming A2A solves cross-organization delegated identity — it secures the hop, not the chain.
- Reaching for A2A to coordinate two agents that live in the same process.
- No answer for how a caller recovers a task after its own connection drops.

## Cheat card

```
DISCOVERY: Agent Card, JSON, published at a well-known path (commonly /.well-known/agent-card.json)
  fetched UNAUTHENTICATED first -> declares skills, securitySchemes, capabilities (streaming, pushNotifications)
  extendedAgentCard: true -> fuller card behind auth via GetExtendedAgentCard

TASK STATES (8): submitted -> working -> {input-required, auth-required} -> completed|failed|canceled|rejected
  input-required/auth-required = durable pause (like interrupt()), NOT a failure

DELIVERY: SSE stream (SendStreamingMessage) + push webhook (on state change) + GetTask polling fallback
  use all three; connections drop, webhooks aren't guaranteed exactly-once

DATA MODEL: Message (role + Parts) · Part = TextPart | FilePart | DataPart · Artifact = task output, chunked
  (append/lastChunk hints for large artifacts)

AUTH: OAuth 2.1 + JWT validation baseline. Agent Cards can be JWT-signed (anti-spoofing).
  cross-hop DELEGATED IDENTITY is NOT standardized -- design your own delegation claim

GOVERNANCE: Linux Foundation (since June 2025) · v1.0 early 2026 · v1.0.1 (May 2026) adds extensions

ADOPTION (honest): 150+ orgs backing (Google, MS, AWS, Salesforce, SAP...) BUT
  most real deployments are still PoCs. backing != production usage. say so.

MCP vs A2A: MCP = agent-to-TOOLS (client/server, resource-shaped)
            A2A = agent-to-AGENT peer (task-shaped, stateful, discoverable)
  COMPOSE: orchestrator uses A2A outward, MCP inward. don't force one to do the other's job.

WHEN NOT TO USE: same-process/same-framework agents -> use native primitives (Send, supervisor)
  synchronous sub-second calls with no pause/stream need -> plain authenticated REST call
```

## Sources

- [A2A Protocol: The Definitive Agent-to-Agent Guide — Tyk](https://tyk.io/learning-center/a2a-protocol-architecture-and-technical-specification/) — well-known URI, three-layer spec structure, 150+ org adoption figure; accessed 2026-08-01
- [Agent2Agent (A2A) Protocol Specification — a2a-protocol.org](https://a2a-protocol.org/latest/specification/) — v1.0.0, eight task states, Agent Card definition, Message/Part/Artifact model, security scheme declaration; accessed 2026-08-01
- [Streaming & Asynchronous Operations — a2a-protocol.org](https://a2a-protocol.org/latest/topics/streaming-and-async/) — SSE streaming, TaskStatusUpdateEvent/TaskArtifactUpdateEvent, push notification webhook behavior; accessed 2026-08-01
- [Security and Authentication — DeepWiki (google/A2A)](https://deepwiki.com/google/A2A/3.2-security-and-authentication) — OAuth 2.1 + JWT baseline, extended agent card auth flow, JWT-signed cards; accessed 2026-08-01
- [Google A2A Protocol in 2026: Adoption, Hype, and Reality — glukhov.org](https://www.glukhov.org/ai-systems/comparisons/a2a-protocol-2026-adoption/) — the PoC-vs-production adoption gap; accessed 2026-08-01
- [MCP vs A2A: The 2026 Guide to AI Agent Protocols — Digital Thought Disruption](https://digitalthoughtdisruption.com/2026/07/25/mcp-vs-a2a-ai-architecture-2026/) — the composition framing, adoption comparison; accessed 2026-08-01
- [Microsoft Agent Framework Overview — Microsoft Learn](https://learn.microsoft.com/en-us/agent-framework/overview/) — native A2A + MCP interoperability in a production-positioned framework; accessed 2026-08-01

## Changelog
- 2026-08-01 — created
