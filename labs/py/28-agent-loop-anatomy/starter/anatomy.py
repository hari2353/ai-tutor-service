"""Lab 28 — agent loop anatomy. Fill in every TODO. Tests define done.

Every stage of one user turn, as pure logic. No LLM, no sleeps, no I/O —
the model is a scripted callable the tests inject.
"""
from __future__ import annotations

import json
from typing import Any, Callable

# Tools that are read-only by convention: allowed with no permission at all.
READ_ONLY_PATTERNS = ("read", "search", "glob", "list", "grep", "find")

# Tools that execute shell commands: need the stronger "execute" permission.
EXECUTE_TOOLS = ("bash", "execute")

# Known side-effecting tools: need "write" permission.
WRITE_TOOLS = ("write", "edit", "delete", "save", "create", "mkdir",
               "apply_patch", "patch", "move", "rename")


# --------------------------------------------------------------------- stage 1
def resolve_tools(user_msg: str, available_tools: list[str],
                  permissions: list[str]) -> list[str]:
    """The subset of `available_tools` this message is allowed to use.

    Rules, per tool name:
      * read-only (contains a READ_ONLY_PATTERN) -> always allowed
      * "bash" / "execute"                       -> needs "execute" permission
      * in WRITE_TOOLS                           -> needs "write" permission
      * anything else                            -> excluded (unknown tool)
    Order of the input is preserved.
    """
    # TODO(step 1)
    raise NotImplementedError


# --------------------------------------------------------------------- stage 2
def build_context(user_msg: str, system_prompt: str, history: list[str],
                  max_history: int) -> list[str]:
    """The message list sent to the model, in order:
      1. system prompt
      2. the LAST max_history entries of history (older ones trimmed)
      3. the user message
    """
    # TODO(step 2)
    raise NotImplementedError


# --------------------------------------------------------------------- stage 3
def parse_model_output(raw: str) -> dict[str, Any]:
    """Parse one raw model output string.

    "TOOL: name {json}"  -> {"type": "tool_use", "tool": name, "args": <dict>}
    plain non-empty text -> {"type": "text", "text": raw}
    bad json after TOOL:,
    or empty/whitespace   -> {"type": "invalid"}
    """
    # TODO(step 3)
    raise NotImplementedError


# --------------------------------------------------------------------- stage 4
def execute_and_observe(tool_call: dict[str, Any],
                        tool_fns: dict[str, Callable[..., Any]],
                        limits: dict[str, int]) -> str:
    """Run one parsed tool call, return the observation string.

    Enforcement:
      * tool not in tool_fns            -> "error: unknown tool"
      * tool raises                     -> "error: <ExceptionType>: <msg>"
      * output longer than limits["max_output_chars"]
                                        -> keep the first max_output_chars
                                           chars, append " [truncated N chars]"
                                           where N is the chars dropped
    A tool's return value is stringified with str().
    """
    # TODO(step 4)
    raise NotImplementedError


# --------------------------------------------------------------------- stage 5
def turn_loop(user_msg: str, fake_model: Callable[[list[str]], str],
              tool_fns: dict[str, Callable[..., Any]],
              config: dict[str, Any]) -> dict[str, Any]:
    """The full turn: context -> model -> parse -> execute -> observe -> repeat.

    * build context from config["system_prompt"], config["history"],
      config["max_history"]
    * call fake_model(context) -> raw string; each call costs one iteration
    * tool_use  -> execute_and_observe with config["limits"], append the
      observation to history, loop
    * text      -> the turn ends; that string is the final text
    * invalid   -> the loop survives: append "error: invalid model output"
      to history and keep going
    * never exceed config["max_iterations"] model calls
    Returns {"final_text": str, "iterations": int, "history": list[str]}
    where history starts with the user message and ends with the final text.
    """
    # TODO(step 5)
    raise NotImplementedError
