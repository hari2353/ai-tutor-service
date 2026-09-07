"""Lab 28 starter — the Agent Review Gauntlet.

Every check is a stub. Make the tests pass. Read the docstrings: they are
the spec, including the honest limits of the heuristics.

Heuristic limits you agree to by using regexes instead of a real parser
(document these in your implementation too — the tests only pin down the
required cases, not arbitrary Python):
  - multi-line strings, multi-target calls and nested brackets can fool
    the line-based scopes in error_handling and no_magic_numbers;
  - no_magic_numbers can't see through f-strings or string joins;
  - hallucinated_api exempts self.<attr> — if the agent writes
    self.push_back() the check stays silent;
  - none of the checks understand string interpolation of variable
    attribute names (getattr(obj, name)).
Your job is the contract in README.md; be robust on the fixtures and
honest in the docstrings.
"""
from __future__ import annotations

import re

SEVERITIES = ("blocker", "warn", "ok")


class CheckResult:
    """Outcome of one check against one file (or one file set).

    passed   -- True if the check found nothing worth flagging
                 (or, for file-set checks, the set satisfies the rule).
    severity -- "blocker" | "warn" | "ok". When something is flagged the
                 severity is that of the finding; when nothing is
                 flagged it must be "ok".
    note     -- "" when passed, else a short human-readable reason.
    """

    def __init__(self, passed: bool, severity: str = "ok", note: str = ""):
        self.passed = passed
        self.severity = severity
        self.note = note

    def __repr__(self) -> str:
        return f"CheckResult(passed={self.passed}, severity={self.severity!r}, note={self.note!r})"


def _ok() -> CheckResult:
    return CheckResult(True, "ok", "")


def _fail(severity: str, note: str) -> CheckResult:
    return CheckResult(False, severity, note)


def _is_test_path(path: str) -> bool:
    """Test fixture: is this file path a test file?

    Must be True when the path contains the substring "test" anywhere
    (that is how the lab defines a test file: tests/test_gauntlet.py,
    test_worker.py, ...). Real tools also look for conftest.py and
    pytest configs; we keep it to the substring rule.
    """
    raise NotImplementedError("is the path a test file? substring rule")


def _defines_tests(code: str) -> bool:
    """Test fixture: does this source define at least one test function?

    True iff a top-level `def test_...` appears in the code.
    (Match def, whitespace, then a name starting with test_ —
    indented defs inside classes count too, that is fine here.)
    """
    raise NotImplementedError("does the file define a test function?")


def has_tests(name: str, code: str, context: dict) -> CheckResult:
    """Check 1: the diff must touch a test file for every source file touched.

    This is a FILE-SET check: `context["files"]` holds the whole diff as
    {path: source}. Pass iff, whenever the set contains at least one
    non-test SOURCE file (.py/.js/.ts/.java/.go — a README/docs-only
    diff contains no source files and passes), it also contains at
    least one test file that defines test_ functions. No source files
    (or no files at all) = pass.

    The interview point: "agent refactored three modules, tests
    untouched" is the classic silent regression, so the gate ties source
    changes to test changes. Limitation: a diff that only deletes files
    would pass; matching test names to the changed modules needs an AST.
    Severity when violated: blocker.
    """
    raise NotImplementedError("every source file touched needs a touched test file")


def no_secrets(name: str, code: str, context: dict) -> CheckResult:
    """Check 2: no hardcoded secrets. Blocker.

    Flag, case by case, all of:
      - AWS access key ids: the regex AKIA[0-9A-Z]{16}
      - a password literal: identifier `password` assigned a quoted
        string via `=` (password = "..."), a quoted "password" key
        followed by a quoted value ({"password": "..."}), or the
        yaml-ish `password: "..."` — but a *variable* value
        (password = os.environ[...]) is fine, and words merely
        containing "password" (change_password(x)) must NOT match;
      - PEM private key headers: BEGIN PRIVATE KEY, BEGIN RSA PRIVATE
        KEY, BEGIN OPENSSH PRIVATE KEY (any case).

    Regexes, not parsers: a secret split across two lines slips through.
    That is why orgs also run entropy scanners (see PRODUCTION.md).
    """
    raise NotImplementedError("find AKIA keys, password literals, PEM private keys")


def error_handling(name: str, code: str, context: dict) -> CheckResult:
    """Check 3: risky calls must be guarded. Warn.

    Risky calls: open(, requests.<anything>, sqlite3.connect(, .execute(,
    .cursor(. A risky call is GUARDED iff the line sits inside a `with`
    block or a `try` block (dedent closes a scope; a with/try line opens
    one). A risky call on the same line as its with (the classic
    `with open(path) as f:`) counts as guarded. Bare = warn.

    Line-based heuristic: it never actually parses the file, so nested
    scopes are handled the way early linters did it. Same line, nested
    blocks, multi-line calls — mostly fine; exotic formatting can lie.
    """
    raise NotImplementedError("open/requests/db calls must sit in a with or try")


def no_magic_numbers(name: str, code: str, context: dict) -> CheckResult:
    """Check 4: no magic numbers. Warn.

    A bare numeric literal > 999 on a line that is NOT an assignment
    (no `=` outside brackets) and NOT a comment/docstring line is
    flagged. Numbers on the RHS of a constant definition are allowed.
    `if x > 1000:` — flagged. `MAX_RETRIES = 1000` — allowed.
    """
    raise NotImplementedError("bare numeric literals > 999 outside assignments")


def naming(name: str, code: str, context: dict) -> CheckResult:
    """Check 5: naming conventions. Warn.

    def names snake_case (lowercase letters, digits, underscores, must
    not be uppercase); class names PascalCase (uppercase first letter,
    no underscores between alpha chars). One finding per violation type
    is enough (do not spam the report per occurrence).

    The interview point: agent-generated identifiers regress to
    camelCase drift when the model was trained on mixed codebases —
    and here you cannot fix what you can't name: the checks below depend
    on a stable naming convention.
    """
    raise NotImplementedError("functions snake_case, classes PascalCase")


def has_docstrings(name: str, code: str, context: dict) -> CheckResult:
    """Check 6: public functions must carry docstrings. Warn.

    A def whose body's first statement is not a string literal has no
    docstring. test_ functions are exempt. One finding is enough.

    Limitation: you count triple-quoted strings, so a leading regular
    string does NOT count, only tripled quotes do. Fine for
    the fixture scripts; a real tool reads code objects.
    """
    raise NotImplementedError("public functions need docstrings, test_ exempt")


def complexity_gate(name: str, code: str, context: dict) -> CheckResult:
    """Check 7: complexity gate. Warn.

    Flag functions longer than 30 lines (def line through end of body,
    blank lines included) or with more than 4 `return` statements
    (unindented prefix spaces stripped before matching `return `).
    For the 40-line test case: a def for a body with ~40 lines between
    the signature and the end of the function (a naive "next line at
    indent < function indent" walk is fine) is flagged.
    """
    raise NotImplementedError("flag functions > 30 lines or > 4 returns")


def hallucinated_api(name: str, code: str, context: dict) -> CheckResult:
    """Check 8: no API calls outside the allowlist. Blocker.

    context["known_apis"] is a set of allowed names. Every attribute
    access `.attr` or method call `.method(` on a value must appear in
    that set, else it is flagged as a possible hallucination. Exempt:
    `.self.` references and the known-safe punctuation attribute names
    {"real", "imag", "group", "groups"}.

    THE agent-specific failure mode: plausible-looking APIs that don't
    exist. list.push_back() looks right if you learned Python from C++
    textbooks. Realistic mitigation: your imports are pinned, so the
    allowlist of what those imports provide is known — flag anything
    outside it. The regex misses chained hallucinations
    (a.b.push_back() still flags; obj.attr.push_back() passes attr) —
    document it, move on.
    """
    raise NotImplementedError("attribute accesses must be in context['known_apis']")


CHECKLIST = [
    (has_tests, "blocker"),
    (no_secrets, "blocker"),
    (hallucinated_api, "blocker"),
    (error_handling, "warn"),
    (no_magic_numbers, "warn"),
    (naming, "warn"),
    (has_docstrings, "warn"),
    (complexity_gate, "warn"),
]


def run_gauntlet(files: dict, context: dict = None) -> dict:
    """Run every check in CHECKLIST over the whole file set.

    Returns {"passed": bool, "findings": [{"file", "check", "severity",
    "note"}, ...]}. A check that flags appends one finding per failed
    file with the check's default severity from CHECKLIST. Any blocker
    finding (severity "blocker") sets passed=False; warns collect but
    never fail the gauntlet.

    has_tests is the file-set check: it runs once, with the whole
    {path: code} passed via context["files"].
    """
    raise NotImplementedError("run the checklist, blockers fail, warns collect")
