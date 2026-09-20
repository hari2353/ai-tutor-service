"""Starter implementation for Lab 32. Replace every stub."""
from dataclasses import dataclass


class BudgetExceeded(RuntimeError):
    pass


@dataclass(frozen=True)
class Slice:
    source_id: str
    version: str
    start: int
    end: int
    text: str


@dataclass(frozen=True)
class ChildResult:
    slice_id: str
    claims: tuple[str, ...]
    evidence: tuple[tuple[int, int], ...]
    status: str
    input_tokens: int
    output_tokens: int


class ContextStore:
    def __init__(self, documents):
        self.documents = documents

    def peek(self, source_id, start=0, end=2000):
        raise NotImplementedError

    def grep(self, term, limit=100):
        raise NotImplementedError


class Budget:
    def __init__(self, max_calls=10, max_depth=2, max_tokens=1000):
        self.max_calls = max_calls
        self.max_depth = max_depth
        self.max_tokens = max_tokens

    def charge(self, tokens, depth):
        raise NotImplementedError


def run_children(question, slices, child, budget, depth=0):
    raise NotImplementedError


def reduce_results(results):
    raise NotImplementedError
