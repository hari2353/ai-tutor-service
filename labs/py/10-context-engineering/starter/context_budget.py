"""Lab 10 — context budget manager. Fill in every TODO. Tests define done.

Message-list items are plain dicts:
    {"role": str, "text": str, "kind": "task"|"constraint"|"tool_result"|"turn"|"recap",
     ...optional "protect": True}

Rules:
  * est_tokens is arithmetic: ceil(len(text) / 4). No tokenizer allowed.
  * task/constraint kinds and protect-flagged items are NEVER altered or evicted.
  * truncate/compact/enforce must preserve the order of surviving items.
"""
from __future__ import annotations

import math
import re
from typing import Callable, Iterable, Sequence

KINDS = ("task", "constraint", "tool_result", "turn", "recap")
COMPACTABLE_KINDS = ("turn", "tool_result")
PROTECTED_KINDS = ("task", "constraint")

# tokens reserved for the truncation marker inside a stubbed tool_result
_STUB_RESERVE = 8
_TRUNC_MARKER_RE = re.compile(r"\[truncated \d+ tokens\]\s*$")


class Unfittable(Exception):
    """enforce() cannot fit the list without breaking protection guarantees."""
    ...


def est_tokens(text: str) -> int:
    """Estimated token count: ceil(len(text) / 4)."""
    # TODO(step 1)
    raise NotImplementedError


def is_protected(item: dict) -> bool:
    """Task/constraint kinds and anything flagged protect=True are untouchable."""
    # TODO(step 2)
    raise NotImplementedError


class ContextBudget:
    def __init__(self, limit: int) -> None:
        if limit < 0:
            raise ValueError("limit must be >= 0")
        self.limit = limit

    def total(self, items: Iterable[dict]) -> int:
        """Sum of est_tokens over all item texts."""
        # TODO(step 3a)
        raise NotImplementedError

    def fits(self, items: Iterable[dict]) -> bool:
        """True when total() <= limit. Empty list always fits."""
        # TODO(step 3b)
        raise NotImplementedError


def truncate_tool_results(items: Sequence[dict], max_per: int = 500) -> list[dict]:
    """Cap every tool_result at max_per tokens.

    Over-cap results keep their head (first (max_per - _STUB_RESERVE) * 4 chars)
    and gain a "\\n[truncated N tokens]" marker, N = tokens dropped; the stubbed
    item stays <= max_per tokens. Non-tool_result kinds, protect-flagged items,
    under-cap results: untouched (same dict objects, same order). Results that
    already carry the marker are skipped — idempotent.
    """
    # TODO(step 4)
    raise NotImplementedError


def _naive_summary(texts: Sequence[str]) -> str:
    """Default summarizer: first line of each text, joined with newlines."""
    # TODO(step 5a)
    raise NotImplementedError


def compact(items: Sequence[dict], keep_recent: int = 4,
            summarizer: Callable[[str], str] | None = None) -> list[dict]:
    """Fold older turns/tool_results into ONE recap item ({"role": "user",
    "text": summary, "kind": "recap"}).

    Never touches task/constraint kinds, protect-flagged items, or the last
    keep_recent compactable items — those pass through with identity preserved.
    The recap replaces the evicted block at the position of its first member.
    With no summarizer use _naive_summary; otherwise call summarizer ONCE with
    the evicted texts joined with "\\n". If nothing is evictable return a
    shallow copy with no recap.
    """
    # TODO(step 5b)
    raise NotImplementedError


def enforce(items: Sequence[dict], limit: int) -> list[dict]:
    """Pipeline: truncate -> compact, repeating, until the list fits limit.

    Raise Unfittable up front when protected items alone exceed limit, and when
    a full truncate+compact round makes no progress while still over budget.
    If the list already fits, return it unchanged (same object, order kept).
    """
    # TODO(step 6)
    raise NotImplementedError
