# Lab 07: MCP Server & Client From Scratch

**Track:** T07 Agentic AI · **Time:** 3h · **XP:** 50
**Module:** `T07-mcp-deep-dive`

**You will build:** an MCP-shaped server and client -- tool registration,
JSON-schema argument validation, JSON-RPC-style request/response framing
over an in-memory transport, and structured error envelopes -- with a
client that discovers tools before it calls them.

**You will be able to answer:** *"Write a minimal MCP server. What's the
difference between a tool that fails and a request that's malformed, and
where does each one show up in the response?"*

## Setup

```bash
cd labs/py/07-mcp-server
python -m venv .venv && . .venv/bin/activate     # or: uv venv && . .venv/bin/activate
pip install pytest                                # only dependency
```

## The spec

1. **`validate_schema(schema, instance)`** -- a teaching-sized subset of
   JSON Schema: `type` (string/integer/number/boolean/array/object/null,
   with `bool` correctly excluded from `integer`/`number`), `properties`,
   `required`, `additionalProperties: false`, `enum`, `minimum`/`maximum`,
   and `items` for arrays. Returns a list of human-readable error strings
   (empty = valid). Never raises.
2. **`MCPServer`** -- `register_tool(ToolSpec)`, then answers two methods:
   `tools/list` (returns each tool's name/description/inputSchema) and
   `tools/call` (validates args against the tool's schema, then executes).
   `handle_request()` and `handle_raw()` **never raise** -- every failure
   becomes a structured envelope.
3. **Two kinds of failure, on purpose** (this is the real MCP split, not a
   lab invention):
   - **Protocol errors** -- malformed frame, unknown method, unknown tool,
     schema-invalid arguments -- become a top-level JSON-RPC `error` object
     (`{"code": ..., "message": ...}`). The *request* was invalid.
   - **Tool execution errors** -- the handler itself raised -- become a
     normal `result` whose payload has `isError: true` and a `content`
     string describing what went wrong. The request was valid; the tool
     just failed while doing its job. This mirrors `dispatch_tool()` from
     Lab 02: a tool exception is data the caller reacts to, not a crash.
4. **`InMemoryTransport`** -- wires a client straight to a server with no
   socket, but still crosses a real `json.dumps`/`json.loads` boundary, so
   a malformed frame (invalid JSON, a JSON array instead of an object,
   missing `method`) behaves the way it would over a real wire.
5. **`MCPClient`** -- `list_tools()` calls `tools/list`; `call_tool(name,
   arguments)` calls `tools/call`. Raises `MCPProtocolError` when the
   *server* rejects the request (unknown tool, invalid params) -- but
   returns a `ToolCallResult(content, is_error=True)` **without raising**
   when the tool itself merely reports failure.

## Run the tests

```bash
pytest tests/ -v          # against starter/ → FAILS. Make them pass.
```

To check the reference: `pytest tests/ -v --solution`

## Stretch goals

1. **Notifications** -- add a fire-and-forget frame shape (no `id`, no
   response expected) and make sure the server doesn't try to reply to one.
   *(Interview: "how do you tell a request from a notification on the
   wire?")*
2. **Resources and prompts** -- add `resources/list` + `resources/read` as
   a second content primitive, app-controlled rather than model-controlled.
   *(Interview: "what's the actual difference between a tool and a
   resource, and who decides which one gets used?")*
3. **Cancellation** -- add a `$/cancel` method that can interrupt an
   in-flight `tools/call` on a slow handler, using the injectable-clock
   pattern from Lab 02 rather than real timeouts.
4. **Confused deputy** -- give a tool a `handler` that "forwards" a
   caller-supplied credential to a fake downstream API, then write a test
   proving the server does *not* silently trust the credential without the
   caller being who they claim -- the trust-boundary problem real MCP
   servers hit in production.
