"""Starter implementation for Lab 31. Replace every stub."""
from dataclasses import dataclass


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
    raise NotImplementedError


def resolve_claims(claims: list[Claim]) -> Decision:
    raise NotImplementedError
