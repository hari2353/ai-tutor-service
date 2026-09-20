"""Reference implementation for Lab 32."""
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

    @property
    def slice_id(self):
        return f"{self.source_id}:{self.version}:{self.start}-{self.end}"


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
        self.documents = dict(documents)

    def peek(self, source_id, start=0, end=2000):
        version, text = self.documents[source_id]
        start = max(0, start)
        end = min(len(text), max(start, end))
        return Slice(source_id, version, start, end, text[start:end])

    def grep(self, term, limit=100):
        term = term.casefold()
        hits = []
        for source_id in sorted(self.documents):
            version, text = self.documents[source_id]
            lower = text.casefold()
            start = 0
            while len(hits) < limit:
                pos = lower.find(term, start)
                if pos < 0:
                    break
                hits.append(self.peek(source_id, max(0, pos - 20), pos + len(term) + 20))
                start = pos + max(1, len(term))
        return hits


class Budget:
    def __init__(self, max_calls=10, max_depth=2, max_tokens=1000):
        self.max_calls = max_calls
        self.max_depth = max_depth
        self.max_tokens = max_tokens
        self.calls = 0
        self.tokens = 0

    def charge(self, tokens, depth):
        if depth > self.max_depth:
            raise BudgetExceeded("max depth")
        if self.calls >= self.max_calls:
            raise BudgetExceeded("max calls")
        if self.tokens + tokens > self.max_tokens:
            raise BudgetExceeded("max tokens")
        self.calls += 1
        self.tokens += tokens


def run_children(question, slices, child, budget, depth=0):
    results = []
    for item in sorted(slices, key=lambda s: s.slice_id):
        estimated = max(1, len(item.text.split()))
        try:
            budget.charge(estimated, depth)
        except BudgetExceeded:
            results.append(ChildResult(item.slice_id, (), (), "budget_exceeded", 0, 0))
            continue
        try:
            result = child(question, item, depth)
            results.append(result)
        except TimeoutError:
            results.append(ChildResult(item.slice_id, (), (), "timeout", estimated, 0))
        except Exception:
            results.append(ChildResult(item.slice_id, (), (), "error", estimated, 0))
    return results


def reduce_results(results):
    claims = []
    evidence = []
    failed = []
    seen = set()
    for result in results:
        if result.status != "ok":
            failed.append(result.slice_id)
            continue
        for claim in result.claims:
            key = claim.casefold().strip()
            if key not in seen:
                seen.add(key)
                claims.append(claim)
        evidence.extend(result.evidence)
    return {
        "claims": tuple(claims),
        "evidence": tuple(evidence),
        "partial": bool(failed),
        "failed_slices": tuple(failed),
    }
