"""Lab 07 -- an MCP-shaped server and client, from scratch, over an
in-memory transport.

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
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    py_type = _TYPE_MAP.get(expected)
    if py_type is None:
        return True  # unknown type keyword in the schema -- don't fail closed
    return isinstance(value, py_type)


def validate_schema(schema: dict, instance: Any, path: str = "arguments") -> list[str]:
    """Validate `instance` against a subset of JSON Schema: type, properties,
    required, additionalProperties, enum, minimum, maximum, items. Returns a
    list of human-readable error strings -- empty means valid. Never raises."""
    errors: list[str] = []
    expected_type = schema.get("type")

    if expected_type and not _check_type(instance, expected_type):
        errors.append(f"{path}: expected {expected_type}, got {type(instance).__name__}")
        return errors  # type mismatch -- deeper structural checks would be noise

    if expected_type == "object":
        props = schema.get("properties", {})
        required = schema.get("required", [])
        for key in required:
            if key not in instance:
                errors.append(f"{path}: missing required field '{key}'")
        if schema.get("additionalProperties") is False:
            extra = sorted(set(instance) - set(props))
            if extra:
                errors.append(f"{path}: unexpected field(s) {extra}")
        for key, value in instance.items():
            if key in props:
                errors.extend(validate_schema(props[key], value, path=f"{path}.{key}"))

    elif expected_type == "array":
        item_schema = schema.get("items")
        if item_schema:
            for i, item in enumerate(instance):
                errors.extend(validate_schema(item_schema, item, path=f"{path}[{i}]"))

    if "enum" in schema and instance not in schema["enum"]:
        errors.append(f"{path}: {instance!r} is not one of {schema['enum']}")
    if "minimum" in schema and isinstance(instance, (int, float)) and instance < schema["minimum"]:
        errors.append(f"{path}: {instance} is less than minimum {schema['minimum']}")
    if "maximum" in schema and isinstance(instance, (int, float)) and instance > schema["maximum"]:
        errors.append(f"{path}: {instance} is greater than maximum {schema['maximum']}")
    return errors


# --------------------------------------------------------------------------- tools
@dataclass
class ToolSpec:
    name: str
    description: str
    input_schema: dict
    handler: Callable[..., Any]

    def describe(self) -> dict:
        return {"name": self.name, "description": self.description, "inputSchema": self.input_schema}


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
        self.tools[tool.name] = tool

    def handle_raw(self, raw: str) -> str:
        """Entry point from the wire: a raw string that might not even be
        valid JSON. Always returns a JSON-encoded envelope string."""
        try:
            frame = json.loads(raw)
        except (json.JSONDecodeError, TypeError) as exc:
            return json.dumps(_error(None, "PARSE_ERROR", f"invalid JSON: {exc}"))
        return json.dumps(self.handle_request(frame))

    def handle_request(self, frame: Any) -> dict:
        """`frame` is already-parsed JSON -- still might be malformed
        (not an object, missing `method`, etc). Never raises."""
        if not isinstance(frame, dict):
            return _error(None, "INVALID_REQUEST", f"frame must be a JSON object, got {type(frame).__name__}")

        id_ = frame.get("id")
        method = frame.get("method")
        if not isinstance(method, str):
            return _error(id_, "INVALID_REQUEST", "frame is missing a required string field 'method'")

        params = frame.get("params")
        if params is None:
            params = {}

        if method == "tools/list":
            return _result(id_, {"tools": [t.describe() for t in self.tools.values()]})
        if method == "tools/call":
            return self._handle_tools_call(id_, params)
        return _error(id_, "METHOD_NOT_FOUND",
                      f"unknown method '{method}'. Available: ['tools/list', 'tools/call']")

    def _handle_tools_call(self, id_: Any, params: Any) -> dict:
        if not isinstance(params, dict):
            return _error(id_, "INVALID_REQUEST", "params must be a JSON object")

        name = params.get("name")
        if not isinstance(name, str):
            return _error(id_, "INVALID_REQUEST", "params.name must be a string")

        tool = self.tools.get(name)
        if tool is None:
            return _error(id_, "UNKNOWN_TOOL", f"unknown tool '{name}'. Available: {sorted(self.tools)}")

        arguments = params.get("arguments", {})
        if arguments is None:
            arguments = {}
        if not isinstance(arguments, dict):
            return _error(id_, "INVALID_PARAMS", "params.arguments must be a JSON object")

        errors = validate_schema(tool.input_schema, arguments)
        if errors:
            return _error(id_, "INVALID_PARAMS", "; ".join(errors))

        try:
            content = tool.handler(**arguments)
        except Exception as exc:  # noqa: BLE001 -- deliberate boundary, mirrors dispatch_tool
            return _result(id_, {"content": f"Error: {type(exc).__name__}: {exc}", "isError": True})
        return _result(id_, {"content": content, "isError": False})


# --------------------------------------------------------------------------- transport
class InMemoryTransport:
    """Wires a client directly to a server with no socket -- but still
    crosses a real serialization boundary (JSON string in, JSON string
    out), so a malformed frame behaves the way it would over the wire."""

    def __init__(self, server: MCPServer) -> None:
        self.server = server

    def request(self, raw: str) -> str:
        return self.server.handle_raw(raw)


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
        id_ = next(self._ids)
        raw = json.dumps({"jsonrpc": "2.0", "id": id_, "method": method, "params": params})
        response = json.loads(self.transport.request(raw))
        error = response.get("error")
        if error is not None:
            raise MCPProtocolError(error.get("code", "UNKNOWN"), error.get("message", ""))
        return response.get("result") or {}

    def list_tools(self) -> list[dict]:
        return self._call("tools/list", {}).get("tools", [])

    def call_tool(self, name: str, arguments: Optional[dict] = None) -> ToolCallResult:
        result = self._call("tools/call", {"name": name, "arguments": arguments or {}})
        return ToolCallResult(content=result.get("content"), is_error=bool(result.get("isError")))
