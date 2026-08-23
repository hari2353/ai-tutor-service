"""Lab 07 tests. Fully in-process, no network, no sockets, no sleeps."""
import pytest


# ------------------------------------------------------------------ step 1: JSON schema validation
def test_validate_schema_valid_instance_has_no_errors(M):
    schema = {"type": "object", "properties": {"q": {"type": "string"}}, "required": ["q"]}
    assert M.validate_schema(schema, {"q": "cats"}) == []


def test_validate_schema_missing_required_field(M):
    schema = {"type": "object", "properties": {"q": {"type": "string"}}, "required": ["q"]}
    errors = M.validate_schema(schema, {})
    assert errors
    assert any("q" in e for e in errors)


def test_validate_schema_wrong_type(M):
    schema = {"type": "object", "properties": {"limit": {"type": "integer"}}, "required": []}
    errors = M.validate_schema(schema, {"limit": "five"})
    assert any("limit" in e and "integer" in e for e in errors)


def test_validate_schema_bool_is_not_integer(M):
    """isinstance(True, int) is True in Python -- the validator must not be fooled."""
    schema = {"type": "object", "properties": {"limit": {"type": "integer"}}, "required": ["limit"]}
    errors = M.validate_schema(schema, {"limit": True})
    assert errors


def test_validate_schema_additional_properties_false_rejects_extra_fields(M):
    schema = {"type": "object", "properties": {"q": {"type": "string"}},
              "required": ["q"], "additionalProperties": False}
    errors = M.validate_schema(schema, {"q": "cats", "shout": True})
    assert any("shout" in e for e in errors)


def test_validate_schema_enum_violation(M):
    schema = {"type": "object", "properties": {"unit": {"type": "string", "enum": ["c", "f"]}}}
    errors = M.validate_schema(schema, {"unit": "kelvin"})
    assert any("unit" in e for e in errors)


def test_validate_schema_min_max(M):
    schema = {"type": "object", "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 10}}}
    assert M.validate_schema(schema, {"limit": 0})
    assert M.validate_schema(schema, {"limit": 11})
    assert M.validate_schema(schema, {"limit": 5}) == []


def test_validate_schema_array_items_type(M):
    schema = {"type": "object", "properties": {"tags": {"type": "array", "items": {"type": "string"}}}}
    assert M.validate_schema(schema, {"tags": ["a", "b"]}) == []
    errors = M.validate_schema(schema, {"tags": ["a", 5]})
    assert any("tags[1]" in e for e in errors)


# ------------------------------------------------------------------ helpers
def _echo_tool(M, calls=None):
    def handler(text):
        if calls is not None:
            calls.append(text)
        return text.upper()
    return M.ToolSpec(
        name="echo",
        description="echoes text back, upper-cased",
        input_schema={"type": "object", "properties": {"text": {"type": "string"}},
                      "required": ["text"], "additionalProperties": False},
        handler=handler,
    )


def _boom_tool(M):
    def handler(text):
        raise ValueError("kaboom")
    return M.ToolSpec(
        name="boom",
        description="always raises",
        input_schema={"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]},
        handler=handler,
    )


def _server_with_echo(M, calls=None):
    server = M.MCPServer()
    server.register_tool(_echo_tool(M, calls))
    return server


# ------------------------------------------------------------------ step 2: server request handling
def test_tools_list_returns_registered_tools(M):
    server = _server_with_echo(M)
    response = server.handle_request({"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}})
    names = [t["name"] for t in response["result"]["tools"]]
    assert names == ["echo"]
    assert "error" not in response


def test_tools_call_success(M):
    server = _server_with_echo(M)
    response = server.handle_request(
        {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
         "params": {"name": "echo", "arguments": {"text": "hi"}}})
    assert response["result"]["content"] == "HI"
    assert response["result"]["isError"] is False


def test_unknown_method_returns_error_envelope_not_raise(M):
    server = _server_with_echo(M)
    response = server.handle_request({"jsonrpc": "2.0", "id": 3, "method": "prompts/list", "params": {}})
    assert response["error"]["code"] == "METHOD_NOT_FOUND"


# ------------------------------------------------------------------ step 3: unknown tool
def test_unknown_tool_returns_useful_error_not_raise(M):
    server = _server_with_echo(M)
    response = server.handle_request(
        {"jsonrpc": "2.0", "id": 4, "method": "tools/call",
         "params": {"name": "ghost", "arguments": {}}})
    assert response["error"]["code"] == "UNKNOWN_TOOL"
    assert "ghost" in response["error"]["message"]


def test_unknown_tool_lists_available_tools_in_message(M):
    server = _server_with_echo(M)
    response = server.handle_request(
        {"jsonrpc": "2.0", "id": 5, "method": "tools/call",
         "params": {"name": "ghost", "arguments": {}}})
    assert "echo" in response["error"]["message"]


# ------------------------------------------------------------------ step 4: malformed frames never raise
@pytest.mark.parametrize("raw", [
    "not json at all {{{",
    "42",
    "null",
    '["a", "list", "not", "an", "object"]',
])
def test_handle_raw_malformed_json_never_raises(M, raw):
    server = _server_with_echo(M)
    out = server.handle_raw(raw)  # must not raise
    envelope = __import__("json").loads(out)
    assert "error" in envelope


def test_handle_request_missing_method_is_invalid_request(M):
    server = _server_with_echo(M)
    response = server.handle_request({"jsonrpc": "2.0", "id": 9, "params": {}})
    assert response["error"]["code"] == "INVALID_REQUEST"


def test_handle_request_not_a_dict_is_invalid_request_not_raise(M):
    server = _server_with_echo(M)
    response = server.handle_request(["totally", "wrong", "shape"])
    assert response["error"]["code"] == "INVALID_REQUEST"


def test_handle_raw_roundtrips_through_real_json(M):
    server = _server_with_echo(M)
    raw = __import__("json").dumps(
        {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
         "params": {"name": "echo", "arguments": {"text": "wire"}}})
    out = server.handle_raw(raw)
    assert isinstance(out, str)
    envelope = __import__("json").loads(out)
    assert envelope["result"]["content"] == "WIRE"


# ------------------------------------------------------------------ step 5: schema rejection at the server
def test_tools_call_invalid_params_useful_error(M):
    server = _server_with_echo(M)
    response = server.handle_request(
        {"jsonrpc": "2.0", "id": 6, "method": "tools/call",
         "params": {"name": "echo", "arguments": {}}})  # missing required 'text'
    assert response["error"]["code"] == "INVALID_PARAMS"
    assert "text" in response["error"]["message"]


def test_tools_call_wrong_type_is_invalid_params(M):
    server = _server_with_echo(M)
    response = server.handle_request(
        {"jsonrpc": "2.0", "id": 7, "method": "tools/call",
         "params": {"name": "echo", "arguments": {"text": 5}}})
    assert response["error"]["code"] == "INVALID_PARAMS"


def test_tools_call_unexpected_arg_is_invalid_params(M):
    server = _server_with_echo(M)
    response = server.handle_request(
        {"jsonrpc": "2.0", "id": 8, "method": "tools/call",
         "params": {"name": "echo", "arguments": {"text": "hi", "shout": True}}})
    assert response["error"]["code"] == "INVALID_PARAMS"


# ------------------------------------------------------------------ step 6: handler exceptions become isError, not raises
def test_tool_handler_exception_becomes_iserror_envelope_not_raise(M):
    server = M.MCPServer()
    server.register_tool(_boom_tool(M))
    response = server.handle_request(
        {"jsonrpc": "2.0", "id": 10, "method": "tools/call",
         "params": {"name": "boom", "arguments": {"text": "x"}}})
    assert "error" not in response or response.get("error") is None
    assert response["result"]["isError"] is True
    assert "kaboom" in response["result"]["content"]


def test_tool_handler_exception_does_not_produce_protocol_error(M):
    """A handler raising is a TOOL failure, not a PROTOCOL failure -- it must
    show up as result.isError, never as a top-level 'error' envelope."""
    server = M.MCPServer()
    server.register_tool(_boom_tool(M))
    response = server.handle_request(
        {"jsonrpc": "2.0", "id": 11, "method": "tools/call",
         "params": {"name": "boom", "arguments": {"text": "x"}}})
    assert response.get("error") is None


# ------------------------------------------------------------------ step 7: client discovery + calling
def test_client_discovers_then_calls_a_tool(M):
    calls = []
    server = _server_with_echo(M, calls)
    client = M.MCPClient(M.InMemoryTransport(server))
    tools = client.list_tools()
    assert [t["name"] for t in tools] == ["echo"]

    result = client.call_tool("echo", {"text": "hi"})
    assert isinstance(result, M.ToolCallResult)
    assert result.content == "HI"
    assert result.is_error is False
    assert calls == ["hi"]


def test_client_call_tool_schema_rejection_raises_useful_error(M):
    server = _server_with_echo(M)
    client = M.MCPClient(M.InMemoryTransport(server))
    with pytest.raises(M.MCPProtocolError) as exc_info:
        client.call_tool("echo", {})  # missing required 'text'
    assert "text" in str(exc_info.value)


def test_client_call_tool_unknown_tool_raises(M):
    server = _server_with_echo(M)
    client = M.MCPClient(M.InMemoryTransport(server))
    with pytest.raises(M.MCPProtocolError) as exc_info:
        client.call_tool("ghost", {})
    assert "ghost" in str(exc_info.value)


def test_client_call_tool_handler_exception_does_not_raise_client_side(M):
    """The protocol-level client call must NOT raise when the tool itself
    fails -- that's business data (isError), not a transport failure."""
    server = M.MCPServer()
    server.register_tool(_boom_tool(M))
    client = M.MCPClient(M.InMemoryTransport(server))
    result = client.call_tool("boom", {"text": "x"})
    assert result.is_error is True
    assert "kaboom" in result.content


def test_client_survives_many_sequential_calls_without_id_collisions(M):
    calls = []
    server = _server_with_echo(M, calls)
    client = M.MCPClient(M.InMemoryTransport(server))
    client.list_tools()
    for letter in ["a", "b", "c"]:
        result = client.call_tool("echo", {"text": letter})
        assert result.content == letter.upper()
    assert calls == ["a", "b", "c"]


def test_multiple_tools_registered_and_listed(M):
    server = M.MCPServer()
    server.register_tool(_echo_tool(M))
    server.register_tool(_boom_tool(M))
    client = M.MCPClient(M.InMemoryTransport(server))
    names = sorted(t["name"] for t in client.list_tools())
    assert names == ["boom", "echo"]
