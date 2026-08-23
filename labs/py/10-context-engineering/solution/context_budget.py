"""Lab 10 — reference solution: context budget manager.

Message-list items are plain dicts:
    {"role": str, "text": str, "kind": "task"|"constraint"|"tool_result"|"turn"|"recap",
     ...optional "protect": True}

Token estimate: ceil(len(text) / 4).
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


def est_tokens(text: str) -> int:
    """Estimated token count: ceil(len(text) / 4)."""
    return math.ceil(len(text) / 4)


def is_protected(item: dict) -> bool:
    """Task/constraint kinds and anything flagged protect=True are untouchable."""
    return bool(item.get("protect")) or item.get("kind") in PROTECTED_KINDS


class ContextBudget:
    def __init__(self, limit: int) -> None:
        if limit < 0:
            raise ValueError("limit must be >= 0")
        self.limit = limit

    def total(self, items: Iterable[dict]) -> int:
        return sum(est_tokens(it["text"]) for it in items)

    def fits(self, items: Iterable[dict]) -> bool:
        return self.total(items) <= self.limit


def truncate_tool_results(items: Sequence[dict], max_per: int = 500) -> list[dict]:
    """Cap every tool_result at max_per tokens.

    Over-cap results keep their head (first (max_per - 8) * 4 chars) and gain a
    "\\n[truncated N tokens]" marker, N = tokens dropped. The stubbed item is
    guaranteed <= max_per tokens. Everything else passes through untouched
    (same dict objects, same order). Already-stubbed results are skipped, so
    the operation is idempotent.
    """
    out: list[dict] = []
    for it in items:
        if (it.get("kind") == "tool_result"
                and not it.get("protect")
                and not _TRUNC_MARKER_RE.search(it["text"])):
            t = est_tokens(it["text"])
            if t > max_per:
                head = it["text"][: max(0, (max_per - _STUB_RESERVE) * 4)]
                dropped = t - est_tokens(head)
                out.append({**it, "text": head + f"\n[truncated {dropped} tokens]"})
                continue
        out.append(it)
    return out


def _naive_summary(texts: Sequence[str]) -> str:
    return "\n".join((t.splitlines() or [""])[0] for t in texts)


def compact(items: Sequence[dict], keep_recent: int = 4,
            summarizer: Callable[[str], str] | None = None) -> list[dict]:
    """Fold older turns/tool_results into ONE recap item.

    Never touches task/constraint kinds, protect-flagged items, or the last
    keep_recent compactable items. Protected and recent items keep identity
    (same dict objects, same relative order). The recap replaces the evicted
    block at the position of its first member. With no summarizer, the naive
    default keeps the first line of each evicted text. A custom summarizer
    receives the evicted texts joined with "\\n", exactly once.
    """
    evictable = [i for i, it in enumerate(items)
                 if it.get("kind") in COMPACTABLE_KINDS and not it.get("protect")]
    if len(evictable) <= keep_recent:
        return list(items)
    evict_idx = set(evictable[:-keep_recent])
    evicted_texts = [items[i]["text"] for i in sorted(evict_idx)]
    summary = (_naive_summary(evicted_texts) if summarizer is None
               else summarizer("\n".join(evicted_texts)))
    recap = {"role": "user", "text": summary, "kind": "recap"}
    out: list[dict] = []
    inserted = False
    for i, it in enumerate(items):
        if i in evict_idx:
            if not inserted:
                out.append(recap)
                inserted = True
        else:
            out.append(it)
    return out


def enforce(items: Sequence[dict], limit: int) -> list[dict]:
    """Pipeline: truncate -> compact, repeating, until the list fits limit.

    Raises Unfittable up front when the protected items alone exceed limit,
    or when no further reduction is possible. Returns the input list object
    itself when it already fits, so order and item identity are preserved.
    """
    budget = ContextBudget(limit)
    protected_total = budget.total(it for it in items if is_protected(it))
    if protected_total > limit:
        raise Unfittable(
            f"protected items alone need {protected_total} tokens > limit {limit}")
    current: Sequence[dict] = items
    for _ in range(len(items) + 4):
        if budget.fits(current):
            return current  # type: ignore[return-value]
        truncated = truncate_tool_results(current)
        if budget.fits(truncated):
            return truncated
        compacted = compact(truncated)
        if compacted == truncated:
            break
        current = compacted
    raise Unfittable(
        f"nothing left to truncate or compact; context exceeds limit {limit}")
