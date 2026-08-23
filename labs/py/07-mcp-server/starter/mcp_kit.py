"""Lab 07 -- an MCP-shaped server and client, from scratch, over an
in-memory transport. Fill in every TODO. Tests define done.

No network, no real `mcp` package: this is a teaching-sized subset of the
Model Context Protocol wire shape (JSON-RPC 2.0 framing, tools/list,
tools/call) that crosses a real serialization boundary (json.dumps /
json.loads) so framing bugs behave the way they would over a socket, while
staying fully in-process and deterministic.

Two kinds of failure, on purpose -- this split is the actual MCP spec, not
an invention for the lab:
  * PROTOCOL errors (malformed frame, unknown method, unknown tool, args
    that fail JSON-schema validation) -> a JSON-RPC `error` object. The
    *request itself* was invalid; MCPClient raises MCPProtocolError.
  * TOOL EXECUTION errors (the handler raised) -> a normal JSON-RPC
    `result` whose payload has `isError: true`. The request was valid; the
    tool just failed while doing its job. This is exactly the same
    philosophy as `dispatch_tool()` in Lab 02: never let a tool exception
    kill the transport, hand it back as data the caller can react to.

Rules:
  * handle_raw() and handle_request() must NEVER raise.
  * MCPClient must raise MCPProtocolError for protocol-level errors, but
    must NOT raise when a tool merely reports isError -- that's data.
"""
from __future__ import annotations

import itertools
import json
from dataclasses import dataclass, field
from typing import Any, Callable, Optional


# --------------------------------------------------------------------------- JSON schema (subset)
_TYPE_MAP = {
    "string": str,
    "boolean": bool,
    "array": list,
    "object": dict,
    "null": type(None),
}


def _check_type(value: Any, expected: str) -> bool:
    """TODO(step 1a): integer/number must reject bool (isinstance(True, int)
    is True in Python -- that's the trap). Fall back to _TYPE_MAP for
    everything else; unknown type keywords should not fail closed."""
    raise NotImplementedError


def validate_schema(schema: dict, instance: Any, path: str = "arguments") -> list[str]:
    """Validate `instance` against a subset of JSON Schema. Returns a list of
    human-readable error strings -- empty means valid. Never raises.

    TODO(step 1b): implement, in order --
      1. type check via _check_type(); on mismatch return early with one
         error "<path>: expected <type>, got <actual type name>"
      2. if type == "object": check `required` keys are present
         ("<path>: missing required field '<key>'"), and if
         additionalProperties is False, flag any keys not in `properties`
         ("<path>: unexpected field(s) [...]"), then recurse into each
         known property with path=f"{path}.{key}"
      3. if type == "array" and schema has "items": recurse into each
         element with path=f"{path}[{i}]"
      4. if schema has "enum" and instance not in it: append an error
      5. if schema has "minimum"/"maximum" and instance is numeric: append
         an error when out of range
    """
    raise NotImplementedError


# --------------------------------------------------------------------------- tools
@dataclass
class ToolSpec:
    name: str
    description: str
    input_schema: dict
    handler: Callable[..., Any]

    def describe(self) -> dict:
        # TODO(step 2a): return {"name":..., "description":..., "inputSchema":...}
        raise NotImplementedError


# --------------------------------------------------------------------------- server
def _error(id_: Any, code: str, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": id_, "error": {"code": code, "message": message}}


def _result(id_: Any, result: dict) -> dict:
    return {"jsonrpc": "2.0", "id": id_, "result": result}


class MCPServer:
    """Registers tools and answers JSON-RPC-shaped frames. `handle_request`
    and `handle_raw` NEVER raise -- every failure mode becomes a structured
    envelope, exactly like `dispatch_tool` in Lab 02."""

    def __init__(self) -> None:
        self.tools: dict[str, ToolSpec] = {}

    def register_tool(self, tool: ToolSpec) -> None:
        # TODO(step 2b): store it in self.tools keyed by name
        raise NotImplementedError

    def handle_raw(self, raw: str) -> str:
        """Entry point from the wire: a raw string that might not even be
        valid JSON. Always returns a JSON-encoded envelope string.

        TODO(step 3a):
          - json.loads(raw); on json.JSONDecodeError/TypeError, return
            json.dumps(_error(None, "PARSE_ERROR", f"invalid JSON: {exc}"))
          - otherwise return json.dumps(self.handle_request(frame))
        """
        raise NotImplementedError

    def handle_request(self, frame: Any) -> dict:
        """`frame` is already-parsed JSON -- still might be malformed
        (not an object, missing `method`, etc). Never raises.

        TODO(step 3b):
          - if frame is not a dict: _error(None, "INVALID_REQUEST", ...)
          - id_ = frame.get("id"); method = frame.get("method")
          - if method is not a str: _error(id_, "INVALID_REQUEST", ...)
          - params = frame.get("params") or {}
          - dispatch: "tools/list" -> _result(id_, {"tools": [t.describe()
            for t in self.tools.values()]})
          - "tools/call" -> self._handle_tools_call(id_, params)
          - anything else -> _error(id_, "METHOD_NOT_FOUND", ...)
        """
        raise NotImplementedError

    def _handle_tools_call(self, id_: Any, params: Any) -> dict:
        """TODO(step 4):
          1. params must be a dict -> else INVALID_REQUEST
          2. params["name"] must be a str -> else INVALID_REQUEST
          3. look up the tool; not found -> UNKNOWN_TOOL, message must
             include the requested name AND the sorted list of available
             tool names
          4. params.get("arguments", {}) must be a dict -> else
             INVALID_PARAMS
          5. validate_schema(tool.input_schema, arguments); non-empty
             errors -> INVALID_PARAMS with "; ".join(errors) as the message
          6. call tool.handler(**arguments); if it raises, catch it and
             return _result(id_, {"content": f"Error: {type(exc).__name__}:
             {exc}", "isError": True}) -- do NOT let it propagate and do
             NOT turn it into a top-level "error"
          7. on success: _result(id_, {"content": content, "isError": False})
        """
        raise NotImplementedError


# --------------------------------------------------------------------------- transport
class InMemoryTransport:
    """Wires a client directly to a server with no socket -- but still
    crosses a real serialization boundary (JSON string in, JSON string
    out), so a malformed frame behaves the way it would over the wire."""

    def __init__(self, server: MCPServer) -> None:
        self.server = server

    def request(self, raw: str) -> str:
        # TODO(step 5a): return self.server.handle_raw(raw)
        raise NotImplementedError


# --------------------------------------------------------------------------- client
class MCPProtocolError(Exception):
    """Raised by MCPClient when the SERVER rejects the request itself
    (malformed frame it sent, unknown tool, schema-invalid args). This is
    distinct from a tool failing while it runs -- see ToolCallResult."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


@dataclass
class ToolCallResult:
    content: Any
    is_error: bool = False


class MCPClient:
    """Discovers tools via tools/list, then calls them via tools/call."""

    def __init__(self, transport: InMemoryTransport) -> None:
        self.transport = transport
        self._ids = itertools.count(1)

    def _call(self, method: str, params: dict) -> dict:
        """TODO(step 5b):
          - id_ = next(self._ids)
          - raw = json.dumps({"jsonrpc": "2.0", "id": id_, "method": method,
            "params": params})
          - response = json.loads(self.transport.request(raw))
          - if response.get("error") is not None: raise MCPProtocolError
            using error["code"] and error["message"]
          - else return response.get("result") or {}
        """
        raise NotImplementedError

    def list_tools(self) -> list[dict]:
        # TODO(step 5c): self._call("tools/list", {}).get("tools", [])
        raise NotImplementedError

    def call_tool(self, name: str, arguments: Optional[dict] = None) -> ToolCallResult:
        """TODO(step 5d): call self._call("tools/call", {"name": name,
        "arguments": arguments or {}}), then wrap the result dict into a
        ToolCallResult(content=..., is_error=bool(result.get("isError")))."""
        raise NotImplementedError
