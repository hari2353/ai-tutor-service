# MCP Deep Dive + FastMCP Server & Client From Scratch

> **Track:** T07 Agentic AI · **Time:** 3.0h · **Prereqs:** none · **Updated:** 2026-08-01
> **Module id:** `T07-mcp-deep-dive` · **Tags:** protocol, mcp
> **Lab:** `labs/py/07-mcp-server/`

## The 30-second version

MCP is JSON-RPC 2.0 messages over a transport — stdio or streamable HTTP — with a version-negotiated `initialize` handshake and three content primitives: tools (model-controlled actions), resources (app-controlled, URI-addressed context), and prompts (user-controlled templates). Two server-initiated escape hatches, sampling and elicitation, let a server ask the connected client's model or user for help mid-call. **This module describes the 2026-07-28 revision**, published four days before this was written, which rewrites the protocol to be stateless — no more session handshake, no more `Mcp-Session-Id` — and deprecates roots, sampling, and logging in favor of doing those things yourself. That revision is brand new; most production servers today still speak 2025-06-18 or 2025-11-25, so both the old and new shapes are fair game. The wire format is deliberately boring; what's hard is the trust boundary. An MCP server acts with its own credentials on behalf of a caller (the model) that can be steered by content it didn't write, which makes every MCP server a confused-deputy risk unless it revalidates every request itself. Use MCP when one tool interface needs to be addressable by multiple heterogeneous clients; skip it for a single in-process function call, where the protocol buys nothing but latency and attack surface.

## Why this gets asked

Because "I used an MCP server" and "I implemented the spec" are different claims, and the gap shows up in the first follow-up question. The tutorial answer is "it's how Claude talks to tools." The shipped answer talks about `isError` versus a JSON-RPC error object, about why a token got forwarded somewhere it shouldn't have, and about the fact that the spec just changed underneath them. The interviewer has personally either debugged an MCP server behind a load balancer that broke under scale-out because of sticky sessions, or reviewed a security incident where a compromised MCP server leaked forwarded user tokens because someone thought passthrough auth was "simpler." They are also checking whether you'll reach for a protocol when a function call would do.

---

## Lineage: past → present → future

**What came before.** Pre-MCP, every framework invented its own tool-calling convention: OpenAI's function calling (June 2023) defined a JSON-schema shape specific to OpenAI's API, LangChain's `Tool` abstraction was a Python interface specific to LangChain, and ChatGPT plugins (March 2023) used a manifest format specific to ChatGPT and died when the ecosystem moved on. The pain was combinatorial: N agent frameworks times M tool providers meant N×M bespoke integrations, no portability, and no standard way for a tool provider to describe its capabilities to a client it had never met. Anthropic released MCP in November 2024 as an explicit answer to that arithmetic, modeled openly on the **Language Server Protocol** — LSP solved "N editors × M languages" by standardizing the wire contract once; MCP applies the same move to "N agent hosts × M tool providers."

**Where it stands now.** Adoption has been fast by infrastructure standards: reported SDK download growth is roughly **970× in sixteen months (100,000 → 97 million monthly)**, and industry surveys report **78% of enterprise AI teams** with at least one MCP-backed agent in production ([Digital Thought Disruption, accessed 2026-08-01](https://digitalthoughtdisruption.com/2026/07/25/mcp-vs-a2a-ai-architecture-2026/)) — treat that specific figure as a secondary-source estimate, not a number from the MCP steering committee. FastMCP is reported to power roughly **70% of MCP servers in the wild** ([KDnuggets, accessed 2026-08-01](https://www.kdnuggets.com/fastmcp-the-pythonic-way-to-build-mcp-servers-and-clients)). The spec itself has moved through five dated revisions in under two years: 2024-11-05 (initial), 2025-03-26 (Streamable HTTP replaces HTTP+SSE, OAuth 2.1 introduced), 2025-06-18 (structured tool output, elicitation, OAuth resource indicators), 2025-11-25 (URL-mode elicitation), and **2026-07-28**, which is the live disagreement made moot by fiat: the spec authors decided state doesn't belong in the protocol layer at all, and rewrote the transport and lifecycle around that position. Not everyone has caught up — this module was written four days after that revision went final, and most SDKs and servers in production right now still implement 2025-06-18 or 2025-11-25 semantics.

**Where it's heading.** High confidence: statelessness wins on pure infrastructure grounds — a stateless server can sit behind a plain round-robin load balancer with no sticky sessions and no shared session store, which is a real operational cost the old design imposed on every remote deployment. This is no longer a debate; it's shipped. Medium confidence: Roots, Sampling, and Logging effectively die over their twelve-month deprecation window, because most serious implementations already do the equivalent themselves — pass a path as a tool argument instead of negotiating a root, call your own model provider instead of asking the client to sample, emit OpenTelemetry instead of a bespoke logging RPC. Speculative: whether the new extensions framework (`io.modelcontextprotocol/tasks`) becomes the standard way to represent long-running async tool calls, replacing the ad hoc "return a job id, poll a status tool" pattern most teams hand-roll today. Treat any confident claim about where MCP "ends up" as provisional; this spec has changed materially four times in twenty months.

---

## Mental model

```
   HOST (Claude Desktop / your agent runtime)
     │
     ├── CLIENT ──1:1──▶ SERVER A  (wraps: your ticketing DB)
     ├── CLIENT ──1:1──▶ SERVER B  (wraps: internal search API)
     └── CLIENT ──1:1──▶ SERVER C  (wraps: filesystem, scoped)

   Each client↔server pair speaks JSON-RPC 2.0 over ONE transport:

     REQUEST      {"jsonrpc":"2.0","id":1,"method":"tools/call","params":{...}}
     RESPONSE     {"jsonrpc":"2.0","id":1,"result":{...}}  |  {"...":"error":{...}}
     NOTIFICATION {"jsonrpc":"2.0","method":"notifications/..."}     ← no id, no reply

   THREE PRIMITIVES, three different deciders:
     tools      → the MODEL decides to call one        (function-calling shaped)
     resources  → the APPLICATION decides to attach one (URI-addressed context)
     prompts    → the USER decides to invoke one         (slash-command-shaped templates)
```

The host owns the fan-out; each client is a dumb 1:1 pipe to one server. Everything interesting — auth, trust, error semantics — lives at that pipe's boundary, not inside the JSON-RPC envelope itself.

---

## How it actually works

### 1. The wire format is JSON-RPC 2.0, nothing more

Requests carry an `id` and expect a response; notifications omit `id` and expect none. That's the entire transport contract — MCP's value is everything layered on top: the methods, the capability negotiation, and the primitives.

### 2. The handshake (as most production servers implement it today)

```
--> {"jsonrpc":"2.0","id":1,"method":"initialize","params":{
       "protocolVersion":"2025-11-25",
       "capabilities":{"roots":{"listChanged":true}},
       "clientInfo":{"name":"my-client","version":"0.1.0"}}}
<-- {"jsonrpc":"2.0","id":1,"result":{
       "protocolVersion":"2025-11-25",
       "capabilities":{"tools":{"listChanged":true},"resources":{}},
       "serverInfo":{"name":"orders-server","version":"0.1.0"}}}
--> {"jsonrpc":"2.0","method":"notifications/initialized"}
--> {"jsonrpc":"2.0","id":2,"method":"tools/call","params":{
       "name":"get_order","arguments":{"order_id":"A-100"}}}
<-- {"jsonrpc":"2.0","id":2,"result":{
       "content":[{"type":"text","text":"{...order json...}"}],"isError":false}}
```

**This handshake is gone as of 2026-07-28.** The stateless rewrite removes `initialize`/`notifications/initialized` entirely: every request now carries its protocol version and client capabilities in `_meta` (`io.modelcontextprotocol/protocolVersion`, `io.modelcontextprotocol/clientCapabilities`), and a new `server/discover` RPC lets a client probe supported versions up front instead of negotiating once per connection. A version mismatch returns `UnsupportedProtocolVersionError`. Say the pre-2026-07-28 shape when asked "walk me through initialize," then volunteer that it's being deleted — that's the current-knowledge signal.

### 3. The three primitives

| Primitive | Who decides | Shape | Methods |
|---|---|---|---|
| **Tools** | The model | JSON-schema in, structured content out | `tools/list`, `tools/call` |
| **Resources** | The application | URI-addressed, subscribable | `resources/list`, `resources/read`, `resources/templates/list` |
| **Prompts** | The user | Named templates with typed arguments | `prompts/list`, `prompts/get` |

The most common conceptual bug is putting something in the wrong bucket: a document search the model should trigger on its own judgment is a tool; a fixed context block the host always attaches is a resource; a human-invoked "summarize document X" slash command is a prompt.

### 4. Transports, and the security shape of each

**stdio** — the server is spawned as a subprocess; JSON-RPC frames flow newline-delimited over stdin/stdout. No network exposure at all: the trust boundary is "whoever can execute this binary on this machine." Cheap, local-only, and the default for developer tooling (Claude Desktop, Cursor). Cold subprocess spawn adds tens of milliseconds before the first request.

**Streamable HTTP** — a single POST endpoint that can optionally upgrade to a streamed (SSE-shaped) response for one request's duration. Prior to 2026-07-28, a server could opt into stateful mode by minting a session via the `Mcp-Session-Id` response header, which every subsequent request from that client had to echo — meaning a load balancer needed sticky sessions or a shared session store to route correctly, and serverless deployments were effectively ruled out because there was no guarantee the instance holding the session was still warm. **2026-07-28 removes `Mcp-Session-Id` and protocol-level sessions entirely**; any instance can now serve any request, and cross-call state, if a server genuinely needs it, is passed as an explicit server-minted handle inside ordinary tool arguments, not a protocol session.

**HTTP+SSE (legacy)** — the original remote transport: two endpoints (a long-lived GET for the SSE stream, a separate POST for messages) with the session tracked by which physical connection was open. Deprecated as a transport choice since **2025-03-26**, and formally reclassified into the **Deprecated** lifecycle state as of **2026-07-28**. Fragile in practice: a dropped SSE stream (proxy timeout, laptop sleep, a serverless platform reaping an idle connection) lost the session with no clean resume, which is exactly the failure the newer transport was built to remove. The 2026-07-28 revision goes further and removes SSE stream resumability (`Last-Event-ID`) from Streamable HTTP too — a broken response stream now means re-issuing the whole request with a new request ID, not resuming.

### 5. Sampling — and its deprecation

`sampling/createMessage` lets a server with no model access of its own ask the connected client to run an LLM completion on its behalf, normally gated by a human-approval step on the client side. It's a real capability — a lightweight server can add "some intelligence" without holding a provider API key — but as of **2026-07-28 sampling is deprecated**, with migration guidance to just call an LLM provider directly with your own key. In practice most serious servers already did that, because depending on the *client's* model and approval UX for your server's behavior is a dependency most people didn't want.

### 6. Elicitation — and how it survives the stateless rewrite

`elicitation/create` lets a server pause mid-tool-call to request structured input it didn't have up front — "which environment should I deploy to" — with the response carrying an `action` of `accept`, `decline`, or `cancel` plus typed `content` on accept. URL-mode elicitation (2025-11-25) added an out-of-band flow for things like OAuth consent screens. Under the stateless 2026-07-28 model there's no server-initiated mid-flight request anymore — the whole pattern moves to **Multi Round-Trip Requests (MRTR)**: the server returns an `InputRequiredResult` (`resultType: "input_required"`) naming what it needs, and the client *retries the original request* with `inputResponses` filled in, rather than the server pushing a fresh request at an already-open connection. Every result now carries a `resultType` field (`"complete"` or `"input_required"`) precisely to make this retry pattern unambiguous.

### 7. Roots — and why removing them doesn't weaken sandboxing

Roots let a client declare which directories or URIs a server is scoped to operate on. It was always advisory, not enforced by the protocol — a well-behaved server was supposed to respect it, but nothing stopped a misbehaving one from ignoring it. Deprecated 2026-07-28 with the suggested migration being what most people did anyway: pass the path as an ordinary tool argument, or bake the scope into server configuration. The real security boundary was always server-side authorization; Roots removes a piece of advisory surface area, not a control.

### 8. Error semantics — the detail that actually ships bugs

Two layers exist and conflating them is the single most common MCP implementation mistake:

- **Protocol-level JSON-RPC errors** — malformed request, unknown method (`-32601`), invalid params (`-32602`) — represent a transport or framework fault. Client SDKs typically raise these as exceptions.
- **Tool execution failures** — the downstream order lookup returned nothing, the API timed out — **must** come back as a normal `tools/call` *result* with `isError: true` and `content` describing what happened, never as a JSON-RPC error.

The reason is the same one covered in `T07-agent-loop-from-scratch` and `T07-tool-engineering`: the model needs to *see* the failure as an observation it can route around. Get this backward — throw a Python exception that a naive server wrapper turns into a JSON-RPC error — and the observable symptom is a client SDK raising mid-await, killing the entire agent run on one flaky downstream call instead of letting the model retry or explain.

### 9. Auth in the HTTP transport

OAuth 2.1 authorization code flow with PKCE for interactive login. **Resource indicators (RFC 8707)**, added in 2025-06-18, scope the issued access token to *this specific* MCP server so it can't be replayed against a different one the client also happens to hold a token for. Authorization responses **should** include `iss` per RFC 9207, and clients **must** validate it against the recorded issuer before redeeming a code — closing a class of authorization-server-mixup attacks. As of 2026-07-28, **Dynamic Client Registration (RFC 7591)** is itself deprecated in favor of **Client ID Metadata Documents**, though DCR remains available for authorization servers that haven't caught up. Client credentials must now be keyed by the issuing authorization server and never reused across a different one.

### 10. The security model: why an MCP server is a confused deputy by construction

A confused deputy is a program that has more authority than the party asking it to act, and is tricked into misusing that authority on the asker's behalf. An MCP server fits this shape exactly: it typically holds its own service credentials to a downstream system, and it acts on instructions that ultimately trace back to a model — a component that can be steered by content it reads, including tool outputs and resource text it did not author (prompt injection). If the server blindly does what the model's current tool call says, an attacker who can get malicious text into any resource or tool result the model reads can cause the server to spend its own elevated privilege on the attacker's behalf.

**Token passthrough is the canonical, spec-forbidden instance of this.** Forwarding the client's bearer token straight to a downstream API (rather than exchanging it for a server-scoped credential) breaks the audit trail — the downstream system logs the *server's* identity, not the real user — bypasses whatever access policy the MCP server was supposed to enforce, and means a single compromised MCP server leaks every live user token that ever passed through it. The MCP authorization spec states this as a **MUST NOT**. The correct pattern: validate the *audience* of the incoming token against your own server's identity, then use a separately obtained, narrowly scoped credential for the actual downstream call — never forward what you were handed.

### 11. Versioning and the revision cadence

MCP versions are dated snapshots of the whole spec, not semver — 2024-11-05, 2025-03-26, 2025-06-18, 2025-11-25, 2026-07-28 — negotiated once at `initialize` historically, or carried per-request under the new stateless model. That cadence is roughly every three to five months, and until 2026-07-28 there was no formal deprecation runway: features could be removed or replaced revision to revision. The 2026-07-28 spec adopts a **feature lifecycle policy** — Active → Deprecated → Removed, with a **minimum twelve-month deprecation window** — specifically in response to the churn the earlier ad hoc approach caused (HTTP+SSE went from "the transport" to gone in under two years).

---

## Build it from scratch

`pip install fastmcp`. This is the current 2025-vintage stateful shape most production servers still speak; it's what you'd actually write today.

### Server

```python
# untested sketch — API verified against gofastmcp.com docs, accessed 2026-08-01
from fastmcp import FastMCP, Context
from pydantic import BaseModel

mcp = FastMCP("orders-server")


@mcp.tool
def get_order(order_id: str) -> dict:
    """Look up an order by id. Returns status and line items."""
    order = db.lookup(order_id)                 # pretend db
    if order is None:
        # Raise here. FastMCP turns this into isError=True content on the
        # tools/call RESULT, not a JSON-RPC protocol error -- the model sees
        # it and can route around it, per the error-semantics section above.
        raise ValueError(f"No order with id {order_id!r}")
    return order.to_dict()


@mcp.resource("orders://{order_id}/invoice")
def invoice(order_id: str) -> str:
    """The rendered invoice text for one order. App-controlled context."""
    return db.lookup(order_id).invoice_text


@mcp.prompt
def refund_request(order_id: str, reason: str) -> str:
    """Template a refund request for a human agent to review."""
    return f"Customer requests refund for order {order_id}. Reason: {reason}"


class ShippingConfirm(BaseModel):
    carrier: str
    tracking: str


@mcp.tool
async def ship_order(order_id: str, ctx: Context) -> str:
    """Mark an order shipped, after confirming carrier/tracking with a human."""
    result = await ctx.elicit(
        f"Confirm shipping details for order {order_id}",
        response_type=ShippingConfirm,
    )
    if result.action != "accept":
        return "Shipping not confirmed; no changes made."
    db.mark_shipped(order_id, result.data.carrier, result.data.tracking)
    return f"Order {order_id} marked shipped via {result.data.carrier}."


if __name__ == "__main__":
    mcp.run(transport="stdio")
    # mcp.run(transport="streamable-http", host="0.0.0.0", port=8000)  # remote
```

### Client

```python
# untested sketch — API verified against gofastmcp.com/clients/client, accessed 2026-08-01
import asyncio
from fastmcp import Client


async def main():
    async with Client("orders_server.py") as client:   # stdio: spawns the subprocess
        tools = await client.list_tools()
        print([t.name for t in tools])

        ok = await client.call_tool("get_order", {"order_id": "A-100"})
        print(ok.data)

        # A tool that raises server-side comes back as content with is_error=True,
        # NOT as a raised Python exception mid-await.
        bad = await client.call_tool("get_order", {"order_id": "does-not-exist"})
        assert bad.is_error


asyncio.run(main())
```

To connect to a remote server instead: `Client("https://api.example.com/mcp")` — the client infers the transport from what you pass it.

The point of building both halves yourself is the same one `T07-agent-loop-from-scratch` makes about the agent loop: once you've written the `initialize` exchange and a `tools/call` round trip by hand, "MCP server" stops meaning "magic Claude Desktop thing" and starts meaning "a JSON-RPC service with three specific method families and one specific error convention" — which is exactly how to describe it in an interview.

---

## How it's done in production

| What production adds | Why it matters |
|---|---|
| **Remote/managed hosting** | Cloudflare's `mcp-remote`, hosted MCP endpoints from vendors — you stop running a subprocess per user session |
| **Auth gateway / token exchange** | A broker in front of many MCP servers that validates the incoming token's audience and exchanges it for a scoped downstream credential, so no individual server implements token passthrough |
| **Observability** | 2026-07-28 formally documents OpenTelemetry trace-context propagation via `_meta` (`traceparent`, `tracestate`, `baggage`), so a tool call is a span in your existing trace, not an opaque black box |
| **Caching** | `ttlMs` and `cacheScope` (`"public"`/`"private"`) on list/read results, new in 2026-07-28, let clients cache `tools/list` output and cut repeated round trips |
| **Rate limiting per tool** | Mutating tools get tighter limits than read-only ones; ties into the risk-tier model in `T07-tool-engineering` |

**What breaks at scale**

| Symptom | Cause | Fix |
|---|---|---|
| Agent run dies with an unhandled client-side exception mid-tool-call | Tool error returned as a JSON-RPC error instead of `isError` content | Catch inside the tool handler; return `isError: true` content, not a protocol error |
| One user can see another user's data through the MCP server | Token passthrough — no audience validation, no re-scoping | Validate token audience server-side; hold your own scoped downstream credential |
| Remote MCP server behind an LB fails intermittently under scale-out | Pre-2026-07-28 stateful mode: `Mcp-Session-Id` requires sticky routing | Sticky sessions / shared session store today; migrate to the stateless transport when your SDK supports it |
| A long tool call silently "forgets" progress after a network blip | Legacy HTTP+SSE transport, connection dropped, no resumability | Move to Streamable HTTP; treat an interrupted call as failed-and-retry, not resumable (2026-07-28 removes `Last-Event-ID` too) |
| A previously-approved tool starts doing something different | Tool poisoning / rug-pull — server changed the tool's description or behavior after the user approved it | Pin a schema/description hash at approval time; re-prompt on any change; treat unpinned third-party MCP servers as untrusted input |
| Model executes instructions found inside a document it just read | Prompt injection via resource or tool-result content | Treat all resource/tool content as data, never instructions; quote/delimit it in the prompt; scope tool permissions to least privilege so a hijacked turn can't do much |

---

## Tradeoffs & when NOT to use MCP

- **A single in-process function call needs no protocol.** MCP adds JSON schema validation, serialization, and — for stdio — a subprocess spawn (tens of milliseconds cold) or — for HTTP — a network round trip, to reach code that a direct function call executes in microseconds. If you're calling a tool fifty times in a loop, that difference is seconds of wall-clock you didn't need to spend.
- **One agent, fixed tools, no other consumer ever.** A hand-rolled tool-calling loop (see `T07-tool-engineering`) is less code, less attack surface, and no dependency on a subprocess or server being reachable. MCP earns its cost when the *same* tool interface needs to be addressable by genuinely different, heterogeneous clients — a Python agent, a teammate's different framework, a desktop app — or when you need real process isolation between the LLM host and the tool, or the tool is a genuine third party you don't control.
- **Wrapping every internal function as an MCP tool "for consistency" is a common overreach.** It converts a function call that cannot fail to be reachable into one with a subprocess or HTTP dependency, for zero portability benefit if nothing outside your own codebase will ever call it.
- **MCP is the wrong layer for agent-to-agent coordination.** It connects an agent to tools and context; it has no task lifecycle, no agent discovery mechanism, and no notion of a peer. Modeling "ask another agent" as an MCP tool call is possible but means reinventing a worse version of what A2A already standardizes — see `T07-a2a-protocol`.

---

## Interview questions

### Q1 — What is MCP, at the wire level?
**Testing:** whether you know it's JSON-RPC or think of it as an opaque SDK feature.
**Answer:** JSON-RPC 2.0 messages — requests, responses, notifications — over a transport (stdio or Streamable HTTP), with a version-negotiated handshake and three primitives layered on top: tools, resources, prompts.
**Follow-up trap:** *"Is it REST?"* — no. JSON-RPC is single-endpoint method dispatch, not resource-oriented HTTP verbs. Confusing the two means misreading Streamable HTTP's single-POST-endpoint design and how a client picks a method to invoke.

### Q2 — Tools vs resources vs prompts — who decides to invoke each?
**Answer:** Tools are model-controlled, like function calling — the LLM decides when to call one. Resources are application-controlled and URI-addressed — the host decides what context to attach, and can subscribe to change notifications. Prompts are user-controlled templates a human explicitly picks. Conflating these three is the most common conceptual bug in an MCP design.
**Follow-up trap:** *"Where do you put a document search?"* — if the model should decide when to search, it's a tool. If the host always attaches the same fixed doc set, it's a resource. If a human explicitly triggers "summarize document X," a prompt template is the right shape.

### Q3 — Walk me through `initialize`.
**Answer:** Client sends `initialize` with `protocolVersion`, `capabilities`, and `clientInfo`; server responds with its own `protocolVersion` (possibly negotiated down to a shared version), `capabilities`, and `serverInfo`; the client sends `notifications/initialized`; only after that can either side call other methods.
**Follow-up trap:** *"What changes in 2026-07-28?"* — this handshake is deleted entirely. Every request carries protocol version and client capabilities in `_meta`, and a `server/discover` RPC replaces up-front negotiation, because the protocol became stateless.

### Q4 — stdio vs Streamable HTTP: when do you pick each?
**Answer:** stdio for local, same-machine tools — spawn as a subprocess, JSON-RPC over stdin/stdout, no network exposure, trust boundary is "who can execute this binary." Streamable HTTP for remote or shared servers — one POST endpoint, optional streamed response, needs OAuth.
**Follow-up trap:** *"What about SSE?"* — the legacy dual-endpoint HTTP+SSE transport, deprecated as a choice since 2025-03-26 and now formally in the Deprecated lifecycle state (2026-07-28). It required sticky sessions because the POST endpoint had to reach the exact instance holding the open SSE stream, which killed horizontal scaling and ruled out serverless deployment.

### Q5 — A tool call fails inside your server. What do you return?
**Answer:** A normal `tools/call` result with `isError: true` and content describing the failure — never a JSON-RPC protocol error. Protocol errors are transport/framework faults; tool failures are data the model needs to see and react to.
**Follow-up trap:** *"What if the failure is a bug in your own tool code, not a bad input?"* — the same distinction `T07-agent-loop-from-scratch` and `T07-tool-engineering` make: a downstream dependency failing is an observation for the model; a harness bug should fail loudly (log/alert), not get silently wrapped into a friendly error string that hides that your code is broken.

### Q6 — What's the confused deputy problem in MCP, concretely?
**Answer:** The server holds its own elevated credentials and acts on behalf of a caller — the model — that can be manipulated by content it reads, including injected instructions inside tool outputs or resource text. If the server trusts that input, an attacker who controls any content the model sees can trick the server into spending its own authority. Token passthrough is the canonical anti-pattern: forwarding the client's bearer token straight to a downstream API breaks the audit trail and, if the server is compromised, leaks every forwarded user token.
**Follow-up trap:** *"How do you fix it?"* — validate the incoming token's audience against your server's own identity, then use a separately held, narrowly scoped credential for the downstream call. Never forward what you were handed.

### Q7 — Sampling: what is it, and what happened to it?
**Answer:** `sampling/createMessage` lets a server without its own model access ask the connected client to run a completion, typically gated by client-side human approval — a way for a lightweight server to borrow "some intelligence" without holding a provider key. As of 2026-07-28 it's deprecated; migration guidance is to call a provider directly with your own key instead.
**Follow-up trap:** *"So is it dead?"* — deprecated, not removed; the new feature lifecycle policy requires a minimum twelve-month window before anything deprecated can even be considered for removal. Plenty of 2025-vintage servers still use it; don't design a new one around it.

### Q8 — What is elicitation, and how is it different from a tool argument?
**Answer:** `elicitation/create` lets a server pause mid-call to ask the user for structured input it didn't have up front, with a typed response (`accept`/`decline`/`cancel` plus data on accept). A tool argument is decided by the model before the call starts; elicitation is decided by the server *during* the call.
**Follow-up trap:** *"How does that work once the protocol is stateless and has no server-initiated requests?"* — it moves to the Multi Round-Trip Request pattern: the server returns an `InputRequiredResult` naming what it needs, and the client retries the *original* request with `inputResponses` filled in, rather than the server pushing a fresh request at an open connection.

### Q9 — Roots are being removed. Does that weaken sandboxing?
**Answer:** No. Roots were always advisory — a well-behaved server was supposed to respect the client-declared scope, but nothing in the protocol enforced it. Deprecated 2026-07-28 because most implementations already passed paths as ordinary tool arguments or baked scope into server config, which is the actual enforcement point.
**Follow-up trap:** *"So where does real sandboxing live?"* — server-side authorization and, for anything executing untrusted code, an actual sandbox (container, gVisor, restricted syscall surface) — see `T07-tool-engineering`'s sandboxing section. Roots was never that.

### Q10 — Design the auth for a remote MCP server proxying a ticketing API.
**Answer:** OAuth 2.1 authorization code flow with PKCE for user login; resource indicators (RFC 8707) so the token is scoped to this specific MCP server and can't be replayed elsewhere; validate `iss` (RFC 9207) against the recorded authorization server before redeeming a code; register the client via Client ID Metadata Documents rather than Dynamic Client Registration, which is now the deprecated path. On the downstream call to the ticketing API, use a separately obtained, narrowly scoped service credential — never the forwarded user token.
**Follow-up trap:** *"Product wants SSO with zero extra login screens."* — that exact pressure is how token-passthrough implementations get shipped. Hold the line and say so; the alternative is a confused-deputy vulnerability by design, not by accident.

### Q11 — Why date-string versions with no semver, and what changed structurally in 2026-07-28?
**Answer:** Each MCP revision is a dated snapshot of the whole interdependent spec, negotiated once (historically) or carried per-request (now). "The spec" isn't a single library with a semver contract — it's a bundle of related features that move together. 2026-07-28 additionally introduced a formal feature lifecycle — Active/Deprecated/Removed with a mandatory twelve-month deprecation window — specifically because earlier revisions (HTTP+SSE's replacement) broke implementers without a structured runway.
**Follow-up trap:** *"What happens if a 2025-11-25 client talks to a 2026-07-28 server?"* — the server can detect the mismatch via the version carried in `_meta` (or a `server/discover` probe) and return `UnsupportedProtocolVersionError`; graceful negotiation across that gap is exactly what `server/discover` exists to make possible.

### Q12 — When is MCP the wrong abstraction?
**Testing:** the senior signal in this whole module.
**Answer:** When it's one agent calling one function in the same process. You're paying schema validation, serialization, and either a subprocess spawn or a network round trip to reach code that's already sitting right there. MCP earns its cost when the same tool must be addressable by multiple heterogeneous clients, when you need real process/security isolation between the LLM host and the tool, or when the tool is a genuine third-party service.
**Follow-up trap:** *"Your team wrapped every internal Python function as an MCP tool 'for consistency.' Good call?"* — no, and say so plainly: that converts a function call that cannot fail to be reachable into one with a subprocess or HTTP dependency, for zero portability benefit if nothing outside your own codebase will ever call it.

### Q13 — Compare MCP to A2A in one paragraph.
**Answer:** MCP connects one agent to tools and context — client-to-server, resource-shaped, the server exposes capabilities the model consumes. A2A connects agents to each other as peers — task-shaped, with an agent card for discovery and a stateful task lifecycle for long-running delegated work. They compose rather than compete: an orchestrating agent might use A2A to hand work to a specialist agent, and that specialist might use MCP to reach its own tools. Full detail in `T07-a2a-protocol`.
**Follow-up trap:** *"Could you build agent-to-agent coordination on top of MCP tools?"* — technically, by modeling "ask agent B" as a tool call, but you lose A2A's task lifecycle, native streaming task updates, and agent-card-based discovery — you'd be reinventing a worse version of A2A.

### Q14 — A remote MCP server behind a load balancer starts failing intermittently as you scale out. Diagnose.
**Answer:** Almost certainly the pre-2026-07-28 stateful Streamable HTTP mode: the server minted an `Mcp-Session-Id`, and follow-up requests for that session must land on the same instance, so plain round-robin routing breaks it. The 2026-07-28 spec removes session-level state from the protocol for exactly this reason — any instance can serve any request once there's no session to pin to an instance.
**Follow-up trap:** *"You can't upgrade the SDK yet — what do you do today?"* — sticky sessions at the load balancer keyed by `Mcp-Session-Id`, or a shared session store if you need cross-instance recovery, and treat an interrupted session as reconnect-and-retry rather than resumable, since SSE/`Last-Event-ID` resumability is gone in the same revision that removes sessions.

---

## Red flags that fail you

- Calling MCP "REST for AI tools."
- Not knowing that tool errors belong in `isError` content, never a JSON-RPC error.
- Recommending token passthrough as "simpler" without naming the confused-deputy risk.
- Believing Roots or Sampling enforce a security boundary.
- Wrapping every in-process function as an MCP tool "for consistency" with no external consumer.
- Confusing MCP with A2A — "we use MCP for multi-agent communication."
- Describing the current transport as HTTP+SSE, or not knowing it's deprecated.
- No answer for "when would you not use MCP."

## Cheat card

```
WIRE: JSON-RPC 2.0. request{id,method,params} / response{id,result|error} / notification (no id)
PRIMITIVES: tools (model-controlled) · resources (app-controlled, URI-addressed) · prompts (user-controlled)
TRANSPORTS: stdio (subprocess, local trust) · Streamable HTTP (1 POST endpoint, optional stream)
  HTTP+SSE: deprecated since 2025-03-26; Deprecated lifecycle state as of 2026-07-28. needed sticky sessions.
SPEC REVISIONS: 2024-11-05 -> 2025-03-26 (Streamable HTTP, OAuth) -> 2025-06-18 (elicitation, RFC 8707)
  -> 2025-11-25 (URL-mode elicit) -> 2026-07-28 (STATELESS: no initialize/sessions; deprecates roots/sampling/logging)
DEPRECATION POLICY (2026-07-28): Active -> Deprecated -> Removed, 12-month minimum window
TOOL ERRORS: isError:true in the tools/call RESULT, never a JSON-RPC error -- model must see it
AUTH: OAuth 2.1 + PKCE · resource indicators (RFC 8707) scope token to ONE server · iss check (RFC 9207)
  DCR (RFC 7591) now deprecated in favor of Client ID Metadata Documents
CONFUSED DEPUTY: token passthrough is a spec MUST NOT. validate audience, hold your OWN downstream credential.
ADOPTION (reported): ~970x SDK downloads in 16mo (100k->97M/mo) · ~78% enterprise teams w/ MCP agent in prod
  · FastMCP ~70% of servers in the wild
WRONG ABSTRACTION: one agent, one in-process function -> skip MCP, call it directly
MCP vs A2A: MCP = agent-to-tools/context. A2A = agent-to-agent peer. they compose.
```

## Sources

- [Key Changes — 2026-07-28 spec changelog](https://modelcontextprotocol.io/specification/2026-07-28/changelog) — the full stateless rewrite, session removal, MRTR, deprecations of Roots/Sampling/Logging, feature lifecycle policy; accessed 2026-08-01
- [The 2026-07-28 MCP Specification Release Candidate — MCP Blog](https://blog.modelcontextprotocol.io/posts/2026-07-28-release-candidate/) — the six SEPs behind statelessness, RC lock date (2026-05-21), final date (2026-07-28); accessed 2026-08-01
- [Key Changes — 2025-11-25 changelog](https://modelcontextprotocol.io/specification/2025-11-25/changelog) — URL-mode elicitation; accessed 2026-08-01
- [Why MCP's Move Away from Server-Sent Events Simplifies Security — Auth0](https://auth0.com/blog/mcp-streamable-http/) — Streamable HTTP vs HTTP+SSE, sticky-session and scaling failure mode; accessed 2026-08-01
- [MCP Authentication and Authorization: OAuth 2.1, Token Delegation, and the Confused Deputy Problem — FlowHunt](https://www.flowhunt.io/blog/mcp-authentication-authorization-oauth-confused-deputy/) — token passthrough as a MUST NOT, the audience-validation fix; accessed 2026-08-01
- [The FastMCP Client — gofastmcp.com](https://gofastmcp.com/clients/client) — client transport inference, `list_tools`/`call_tool` API; accessed 2026-08-01
- [Sampling — gofastmcp.com](https://gofastmcp.com/servers/sampling) — `ctx.sample()` API and its deprecation notice; accessed 2026-08-01
- [MCP vs A2A: The 2026 Guide — Digital Thought Disruption](https://digitalthoughtdisruption.com/2026/07/25/mcp-vs-a2a-ai-architecture-2026/) — adoption figures (970x downloads, 78% enterprise teams); reported secondary-source estimate, accessed 2026-08-01
- [FastMCP: The Pythonic Way to Build MCP Servers and Clients — KDnuggets](https://www.kdnuggets.com/fastmcp-the-pythonic-way-to-build-mcp-servers-and-clients) — the ~70%-of-servers estimate; accessed 2026-08-01
- [Model Context Protocol prepares to break with its stateful past — The Register](https://www.theregister.com/devops/2026/07/23/model-context-protocol-prepares-to-break-with-its-stateful-past/5276722) — practitioner-facing summary of the stateless rewrite and its infra motivation; accessed 2026-08-01

## Changelog
- 2026-08-01 — created
- 2026-08-09 — MCP spec **2026-07-28** shipped as final (supersedes the 2025-11-25 revision): protocol goes stateless — `initialize`/`initialized` handshake and `Mcp-Session-Id` removed, replaced by per-request `_meta` fields and a new `server/discover` RPC; HTTP GET + `resources/subscribe`/`unsubscribe` replaced by a single `subscriptions/listen` stream; `ping`, `logging/setLevel`, and root-list-changed notifications removed; Roots, Sampling, and Logging are now **deprecated** (12-month window; migrate to tool params, direct provider APIs, and OTel/stderr logging respectively); HTTP+SSE transport reclassified Deprecated; OAuth Dynamic Client Registration deprecated in favor of Client ID Metadata Documents; new Multi Round-Trip Requests (MRTR) pattern replaces server-initiated requests with an `InputRequiredResult`/`resultType` retry flow — this changes the correct answer to "how does an MCP server ask the client for more info mid-call" ([src](https://modelcontextprotocol.io/specification/2026-07-28/changelog))
  - *Interview angle:* "Walk me through how an MCP client and server negotiate a session" — the old initialize-handshake answer is now wrong; the protocol is stateless and version negotiation happens per-request or via `server/discover`.
