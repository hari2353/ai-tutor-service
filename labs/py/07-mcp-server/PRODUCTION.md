# Production notes -- MCP servers

## What you'd actually use

| Concern | Roll-your-own (this lab) | Production reach-for |
|---|---|---|
| Server/client SDK | ~230 lines, hand-rolled | `mcp` (the official Python SDK) or `FastMCP`, which handle the handshake, capability negotiation, and transports for you |
| Transport | in-memory function call | stdio (local subprocess) or streamable HTTP (remote); both need real framing, backpressure, and reconnect logic |
| Schema validation | a ~40-line subset (type/required/enum/min/max/items) | full JSON Schema via `jsonschema` or `pydantic`, including `$ref`, `oneOf`/`anyOf`, `pattern`, nested `additionalProperties` |
| Error shape | 5 hand-picked codes | JSON-RPC 2.0's numeric codes (`-32700` parse error, `-32601` method not found, `-32602` invalid params) plus MCP's `isError` convention for tool-level failures |
| Auth | none -- there's no caller identity | OAuth 2.1 for remote servers, or inherited process credentials for local stdio servers; every tool call needs to know *whose* credentials it's running with |
| Discovery | one static tool list | dynamic tool lists that change at runtime, `notifications/tools/list_changed` to tell the client to re-fetch |

## What the real ones add over yours

- **Version-negotiated handshake.** Real MCP opens with an `initialize`
  exchange where client and server agree on a protocol version and
  advertise capabilities (does this server support resources? sampling?).
  This lab skips it because the two-error-classes distinction is the part
  that actually shows up in interviews; the handshake is boilerplate you'd
  get from the SDK either way.
- **Real JSON Schema, not a subset.** `isinstance` and a hand-written
  `enum`/`minimum` check catch the common cases. They don't catch a regex
  `pattern`, a `oneOf` across three shapes, or a schema that references
  another schema by `$ref` -- and that gap is exactly where a model
  constructs a plausible-looking but invalid tool call that slips through.
- **The confused-deputy problem.** An MCP server acts with *its own*
  credentials on behalf of a caller (the model) that can be steered by
  content it didn't write -- a prompt injection buried in a document the
  model reads can cause the server to call a privileged tool the human
  never asked for. Production servers revalidate every request against the
  authenticated caller's actual permissions; they don't trust that "the
  model asked nicely" is authorization.
- **Passthrough auth is a trap, not a shortcut.** Forwarding a user's
  bearer token straight through to a downstream API "because it's
  simpler" means the MCP server never actually checks scope -- if the
  token has more access than the tool should grant, the server just
  handed it over. This has caused real security incidents.
- **Sticky sessions break scale-out.** A streamable-HTTP MCP server behind
  a load balancer that round-robins requests will drop a session
  mid-conversation unless requests are pinned to the instance that holds
  the session state (or state is externalized to a shared store). This
  lab's in-memory transport has no such problem because there's only one
  process -- production has many.

## What breaks at scale

| Symptom | Cause | Fix |
|---|---|---|
| A model's tool call silently does the wrong thing | Schema validation too shallow to catch a semantically-wrong-but-type-valid argument (e.g. a currency code that isn't in the real enum) | Full JSON Schema with `enum`/`pattern`, and business-rule validation inside the handler as a second layer |
| One compromised MCP server exfiltrates a user's token | Passthrough auth: the server forwards a bearer token to a downstream API without checking the caller is authorized for that specific action | Server mints its own scoped, short-lived credentials per request instead of forwarding the caller's token verbatim |
| Load-balanced MCP server drops sessions under traffic | Sticky-session requirement with round-robin routing, or session state kept only in one process's memory | Session affinity at the LB, or externalize session state to Redis/a database |
| Client hangs forever on a slow tool | No cancellation support, no timeout budget on the call | `$/cancel` notifications plus a client-side deadline (same shape as the `Budget.deadline_seconds` pattern from Lab 02) |
| A tool that "sometimes" fails looks like a transport bug | Handler exceptions leaking as top-level JSON-RPC errors instead of `isError: true` results, so the model can't distinguish "your request was bad" from "the tool tried and failed" | Keep tool-execution failures inside `result.isError`, exactly as this lab does |

## Cost & latency

MCP itself adds negligible latency on a local stdio transport (single-digit
milliseconds for framing/parsing) but a remote streamable-HTTP server adds a
full network round trip per tool call -- 20-100ms same-region, more across
regions -- which matters when an agent makes 10-20 tool calls per task. The
real cost driver isn't the protocol, it's the number of round trips: a
server that requires three sequential calls to do what one well-designed
tool could do in one call multiplies both latency and token spend (each
call's result goes back into the model's context).

## The 3 questions an interviewer asks after you describe this

1. *"A tool handler raises. Where does that show up in the response, and
   why not just as a JSON-RPC error?"* -- as `result.isError: true`, because
   the request itself was valid; putting it in the top-level `error` field
   would make the client's retry/backoff logic (which is keyed on protocol
   errors) treat a routine tool failure as a broken connection.
2. *"Your server trusts whatever tool name and arguments arrive over the
   transport. What's missing for a real deployment?"* -- authorization tied
   to the actual caller identity, not just schema validity; a
   syntactically valid `tools/call` for `delete_account` can still be a
   confused-deputy attack if nothing checks whether this caller, in this
   context, is allowed to invoke it.
3. *"How would this behave differently over streamable HTTP instead of
   your in-memory transport?"* -- you'd need to handle partial reads,
   connection drops mid-response, backpressure when the client is slow to
   consume a streamed result, and (per the 2026-07-28 protocol revision)
   no session ID to correlate requests if the server is meant to be
   stateless across scale-out replicas.
