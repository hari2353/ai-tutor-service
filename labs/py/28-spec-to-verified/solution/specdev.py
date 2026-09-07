"""Lab 28 — the spec → build → verify loop as executable logic."""
from __future__ import annotations

from typing import Callable


class Spec:
    """A mini spec: the executable half only.

    'REQ <id>: <description>' lines become requirements; 'ACCEPT <req_id>:
    <criterion>' lines attach acceptance criteria to the requirement id.
    Headers, prose, blank lines and REQ/ACCEPT lines missing their colon are
    ignored — if it does not parse, it is not part of the contract.
    """

    def __init__(self, text: str) -> None:
        self.requirements: dict[str, str] = {}
        self.criteria: dict[str, list[str]] = {}
        for raw in text.splitlines():
            line = raw.strip()
            if line.startswith("REQ "):
                req_id, sep, description = line[4:].partition(":")
                if sep:
                    self.requirements[req_id.strip()] = description.strip()
            elif line.startswith("ACCEPT "):
                req_id, sep, criterion = line[7:].partition(":")
                if sep:
                    self.criteria.setdefault(req_id.strip(), []).append(criterion.strip())


def verify(requirements: dict, criteria: dict, implementation: dict) -> dict:
    """Judge the builder's self-report against the spec. The spec owns the check.

    A criterion the self-report never mentions is failed — absence of
    evidence is not done. A requirement with no criteria fails by default:
    unverifiable is not done. Requirement ids in the implementation that are
    not in the spec are hallucinated: listed under the report's reserved
    'hallucinated' key, given no entry of their own, and counted as neither
    pass nor fail.
    """
    report: dict = {}
    for req_id in requirements:
        required = criteria.get(req_id, [])
        if not required:
            report[req_id] = {"passed": False, "failed_criteria": []}
            continue
        claimed = implementation.get(req_id, {})
        failed = [c for c in required if not claimed.get(c, False)]
        report[req_id] = {"passed": not failed, "failed_criteria": failed}
    report["hallucinated"] = sorted(
        req_id for req_id in implementation if req_id not in requirements
    )
    return report


def _all_passed(report: dict) -> bool:
    return all(
        entry["passed"]
        for req_id, entry in report.items()
        if req_id != "hallucinated"
    )


def run_spec(spec: Spec, builder: Callable, max_rounds: int = 3) -> dict:
    """Build → verify → feed failures back, until green or out of rounds.

    Round 1 calls builder(requirements); every later round calls
    builder(requirements, prev_implementation, report), so a builder that
    wants to converge accepts the previous attempt and the failure report
    and fixes what the report names. An empty spec is trivially done: the
    builder never runs.
    """
    if not spec.requirements:
        return {"implementation": {}, "rounds": 0, "all_passed": True}
    implementation: dict = {}
    report = verify(spec.requirements, spec.criteria, implementation)
    rounds = 0
    while not _all_passed(report) and rounds < max_rounds:
        rounds += 1
        if rounds == 1:
            implementation = builder(spec.requirements)
        else:
            implementation = builder(spec.requirements, implementation, report)
        report = verify(spec.requirements, spec.criteria, implementation)
    return {
        "implementation": implementation,
        "rounds": rounds,
        "all_passed": _all_passed(report),
    }
