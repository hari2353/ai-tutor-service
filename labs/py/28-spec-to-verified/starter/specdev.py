"""Lab 28 — the spec → build → verify loop as executable logic. Fill in every TODO.

Rules:
  * The spec owns the criteria — the implementation is judged only against what
    the spec names, and a criterion the self-report never mentions is failed.
  * Unverifiable is not done — a requirement with no acceptance criteria fails
    by default.
  * Requirement ids the spec never contained are hallucinated: reported,
    ignored, never counted as passing anything.
"""
from __future__ import annotations

from typing import Callable


class Spec:
    """Parse the mini spec format.

    'REQ <id>: <description>'      -> self.requirements = {id: description}
    'ACCEPT <req_id>: <criterion>' -> self.criteria = {req_id: [criterion, ...]}

    Headers, prose and blank lines are ignored, as are REQ/ACCEPT lines that
    never reach their colon. Multiple ACCEPT lines for one requirement append
    in order. An ACCEPT may reference an id with no REQ — it parses, but
    nothing ever verifies it.
    """

    def __init__(self, text: str) -> None:
        self.requirements: dict[str, str] = {}
        self.criteria: dict[str, list[str]] = {}
        # TODO(step 1): walk the lines and fill both dicts.
        raise NotImplementedError


def verify(requirements: dict, criteria: dict, implementation: dict) -> dict:
    """Judge a self-reported implementation against the spec's criteria.

    implementation is {req_id: {criterion: bool}} — the builder's claim, or a
    test run's verdicts. Returns {req_id: {"passed": bool, "failed_criteria":
    [...]}} plus one reserved "hallucinated" key: the sorted requirement ids
    present in the implementation but absent from the spec. A requirement
    with no criteria fails with an empty failed_criteria list — nothing
    failed, it simply cannot be verified. Hallucinated ids get no report
    entry and can make nothing pass or fail.
    """
    # TODO(step 2): judge every requirement against its own criteria only.
    raise NotImplementedError


def run_spec(spec: "Spec", builder: Callable, max_rounds: int = 3) -> dict:
    """The loop: build → verify → feed failures back, until green or out of rounds.

    Round 1 calls builder(spec.requirements). Every later round calls
    builder(spec.requirements, prev_implementation, report) — the previous
    attempt and the failure report — so a builder that intends to converge
    accepts those two extra arguments. An empty spec is trivially done: the
    builder never runs and the result is {"implementation": {}, "rounds": 0,
    "all_passed": True}. Returns {"implementation": ..., "rounds": ...,
    "all_passed": ...}.
    """
    # TODO(step 3): loop, verify, decide.
    raise NotImplementedError
