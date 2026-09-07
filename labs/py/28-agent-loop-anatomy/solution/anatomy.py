"""Lab 28 — reference solution: one agent turn, dissected into pure stages."""
from __future__ import annotations

import json
from typing import Any, Callable

READ_ONLY_PATTERNS = ("read", "search", "glob", "list", "grep", "find")
EXECUTE_TOOLS = ("bash", "execute")
WRITE_TOOLS = ("write", "edit", "delete", "save", "create", "mkdir",
               "apply_patch", "patch", "move", "rename")


def resolve_tools(user_msg: str, available_tools: list[str],
                  permissions: list[str]) -> list[str]:
    allowed: list[str] = []
    perms = set(permissions)
    for name in available_tools:
        lowered = name.lower()
        if any(p in lowered for p in READ_ONLY_PATTERNS):
            allowed.append(name)
        elif lowered in EXECUTE_TOOLS:
            if "execute" in perms:
                allowed.append(name)
        elif lowered in WRITE_TOOLS:
            if "write" in perms:
                allowed.append(name)
        # else: unknown tool -> excluded regardless of permissions
    return allowed


def build_context(user_msg: str, system_prompt: str, history: list[str],
                  max_history: int) -> list[str]:
    trimmed = list(history[-max_history:]) if max_history > 0 else []
    return [system_prompt, *trimmed, user_msg]


def parse_model_output(raw: str) -> dict[str, Any]:
    if not raw or not raw.strip():
        return {"type": "invalid"}
    if raw.startswith("TOOL:"):
        rest = raw[len("TOOL:"):].strip()
        if " " not in rest and "{" not in rest:
            return {"type": "invalid"}
        name, _, json_part = rest.partition(" ")
        try:
            args = json.loads(json_part)
        except (ValueError, TypeError):
            return {"type": "invalid"}
        if not isinstance(args, dict):
            return {"type": "invalid"}
        return {"type": "tool_use", "tool": name, "args": args}
    return {"type": "text", "text": raw}


def execute_and_observe(tool_call: dict[str, Any],
                        tool_fns: dict[str, Callable[..., Any]],
                        limits: dict[str, int]) -> str:
    name = tool_call["tool"]
    args = tool_call.get("args", {})
    if name not in tool_fns:
        return "error: unknown tool"
    try:
        out = tool_fns[name](**args)
    except Exception as exc:
        return f"error: {type(exc).__name__}: {exc}"
    obs = out if isinstance(out, str) else str(out)
    cap = limits["max_output_chars"]
    if len(obs) > cap:
        dropped = len(obs) - cap
        obs = obs[:cap] + f" [truncated {dropped} chars]"
    return obs


def turn_loop(user_msg: str, fake_model: Callable[[list[str]], str],
              tool_fns: dict[str, Callable[..., Any]],
              config: dict[str, Any]) -> dict[str, Any]:
    prior_history: list[str] = list(config.get("history") or [])
    observations: list[str] = []          # what this turn has seen so far
    transcript: list[str] = [user_msg]   # the "history" we return
    max_iterations = config["max_iterations"]
    iterations = 0

    while iterations < max_iterations:
        context = build_context(user_msg, config.get("system_prompt", ""),
                                prior_history + observations,
                                config.get("max_history", 10))
        raw = fake_model(context)
        iterations += 1
        parsed = parse_model_output(raw)

        if parsed["type"] == "text":
            transcript.append(parsed["text"])
            return {"final_text": parsed["text"], "iterations": iterations,
                    "history": transcript}

        if parsed["type"] == "tool_use":
            obs = execute_and_observe(parsed, tool_fns,
                                      config.get("limits",
                                                 {"max_output_chars": 10_000}))
            observations.append(obs)
            transcript.append(obs)
            continue

        # invalid — the loop survives a bad model output
        transcript.append("error: invalid model output")

    return {"final_text": "", "iterations": iterations, "history": transcript}
