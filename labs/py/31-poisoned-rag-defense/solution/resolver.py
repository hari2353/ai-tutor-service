"""Reference implementation for Lab 31."""
from dataclasses import dataclass
import re


@dataclass(frozen=True)
class Claim:
    value: str
    source_id: str
    tier: int
    approved: bool = True


@dataclass(frozen=True)
class Decision:
    status: str
    value: str | None
    sources: tuple[str, ...]


def normalize_value(value: str) -> str:
    text = " ".join((value or "").strip().split())
    numeric = re.sub(r"(?:rs\.?|inr|usd|\$|€|£|₹|,|\s)", "", text.casefold())
    if re.fullmatch(r"[-+]?\d+(?:\.\d+)?", numeric):
        return numeric
    return text.casefold()


def resolve_claims(claims: list[Claim]) -> Decision:
    usable = [c for c in claims if c.approved and normalize_value(c.value)]
    if not usable:
        return Decision("abstained", None, ())

    groups: dict[str, list[Claim]] = {}
    for claim in usable:
        groups.setdefault(normalize_value(claim.value), []).append(claim)
    if len(groups) == 1:
        value, members = next(iter(groups.items()))
        tier = max(c.tier for c in members)
        status = "answered" if tier >= 2 else "hedged"
        return Decision(status, value, tuple(c.source_id for c in members))

    ranked = sorted(
        groups.items(),
        key=lambda item: (-max(c.tier for c in item[1]), item[0]),
    )
    winner, members = ranked[0]
    winner_tier = max(c.tier for c in members)
    tied = [item for item in ranked if max(c.tier for c in item[1]) == winner_tier]
    if len(tied) != 1:
        return Decision("abstained", None, tuple(c.source_id for c in usable))
    status = "answered" if winner_tier >= 2 else "hedged"
    return Decision(status, winner, tuple(c.source_id for c in members))
