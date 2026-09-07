"""Lab 28 reference solution — the Agent Review Gauntlet.

Regex-and-indent heuristics throughout. They are honest about what they
can't see; see each check's docstring for its misses. They catch the
required cases, which is how the first linters shipped too.
"""
from __future__ import annotations

import re

SEVERITIES = ("blocker", "warn", "ok")

# ------------------------------------------------------------------ shared
_RE_DEF = re.compile(r"^\s*def\s+(\w+)\s*\(")
_RE_CLASS = re.compile(r"^\s*class\s+(\w+)")
_RE_AKIA = re.compile(r"\bAKIA[0-9A-Z]{16}\b")
_RE_PEM = re.compile(r"-----BEGIN (?:RSA |OPENSSH )?PRIVATE KEY-----")
_RE_PASSWORD = re.compile(
    r"password\s*=\s*[\"'][^\"']+[\"']"                     # password = "literal"
    r"|[\"']password[\"']\s*[:=]\s*[\"'][^\"']+[\"']"       # "password": "literal"
    r"|\bpassword\s*:\s*[\"'][^\"']+[\"']",                 # password: "literal" (yaml-ish)
    re.IGNORECASE,
)
_RE_RISKY = re.compile(r"open\(|requests\.|sqlite3\.connect\(|\.execute\(|\.cursor\(")
_RE_WITH = re.compile(r"^\s*with\b")
_RE_TRY = re.compile(r"^\s*try\b")
_RE_ASSIGN = re.compile(r"=[^=]")
_RE_NUMBER = re.compile(r"(?<![\w.])\d+(?:\.\d+)?(?:[eE][+-]?\d+)?(?![\w.])")
_RE_ATTR = re.compile(r"\.(\w+)\s*\(")
_RE_ACCESS = re.compile(r"\.(\w+)\b(?!\s*\()")
_SAFE_ATTRS = {"real", "imag", "group", "groups"}


class CheckResult:
    def __init__(self, passed: bool, severity: str = "ok", note: str = ""):
        self.passed = passed
        self.severity = severity
        self.note = note

    def __repr__(self) -> str:
        return f"CheckResult(passed={self.passed}, severity={self.severity!r}, note={self.note!r})"


def _ok():
    return CheckResult(True, "ok", "")


def _fail(severity, note):
    return CheckResult(False, severity, note)


def _is_test_path(path):
    return "test" in path.lower()


def _defines_tests(code):
    return re.search(r"^\s*def\s+test_\w+", code, re.MULTILINE) is not None


# ------------------------------------------------------------------ checks
def has_tests(name, code, context):
    """A README/docs-only changeset contains no source files at all, so
    the "every source file needs a test" rule is vacuously satisfied."""
    files = (context or {}).get("files", {}) or {}
    sources = [p for p in files
               if not _is_test_path(p) and p.lower().endswith((".py", ".js", ".ts", ".java", ".go"))]
    if not sources:
        return _ok()
    for p, src in files.items():
        if _is_test_path(p) and _defines_tests(src):
            return _ok()
    return _fail(
        "blocker",
        "source files changed but no test file in the changeset "
        "(agent refactors must ship with tests)",
    )


def no_secrets(name, code, context):
    if _RE_AKIA.search(code):
        return _fail("blocker", "hardcoded AWS access key id (AKIA...)")
    if _RE_PEM.search(code):
        return _fail("blocker", "PEM private key material in source")
    if _RE_PASSWORD.search(code):
        return _fail("blocker", "hardcoded password literal")
    return _ok()


def error_handling(name, code, context):
    stack = []  # entries: True = with/try scope, False = other block
    for line in code.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(line) - len(line.lstrip())
        while stack and stack[-1][1] > indent:
            stack.pop()
        if _RE_WITH.match(line) or _RE_TRY.match(line):
            stack.append((True, indent))
        else:
            if re.match(r"^\s*(def |class |async def )", line):
                stack.append((False, indent))
            elif stripped.endswith(":"):
                stack.append((False, indent))
            if _RE_RISKY.search(line) and not (stack and stack[-1][0]):
                return _fail(
                    "warn",
                    "unguarded risky call (open/requests/db) outside with/try: "
                    + stripped[:60],
                )
    return _ok()


def no_magic_numbers(name, code, context):
    for line in code.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if _RE_ASSIGN.search(line):
            continue
        for m in _RE_NUMBER.finditer(stripped):
            if float(m.group(0)) > 999:
                return _fail(
                    "warn",
                    "magic number %s outside a constant assignment" % m.group(0),
                )
    return _ok()


def naming(name, code, context):
    for line in code.splitlines():
        m = _RE_DEF.match(line)
        if m and not re.fullmatch(r"[a-z_][a-z0-9_]*", m.group(1)):
            return _fail("warn", "function %r is not snake_case" % m.group(1))
        m = _RE_CLASS.match(line)
        if m:
            cls = m.group(1)
            if not re.match(r"[A-Z]", cls) or "_" in cls:
                return _fail("warn", "class %r is not PascalCase" % cls)
    return _ok()


def has_docstrings(name, code, context):
    lines = code.splitlines()
    for i, line in enumerate(lines):
        m = _RE_DEF.match(line)
        if not m or m.group(1).startswith("test_"):
            continue
        for j in range(i + 1, len(lines)):
            body = lines[j].strip()
            if not body or body.startswith("#"):
                continue
            if body.startswith('"""') or body.startswith("'''"):
                break
            return _fail("warn", "function %r has no docstring" % m.group(1))
    return _ok()


def complexity_gate(name, code, context):
    lines = code.splitlines()
    for i, line in enumerate(lines):
        m = _RE_DEF.match(line)
        if not m:
            continue
        findent = len(line) - len(line.lstrip())
        returns = 0
        length = 1
        for j in range(i + 1, len(lines)):
            l = lines[j]
            if l.strip():
                indent = len(l) - len(l.lstrip())
                if indent <= findent:
                    break
            length += 1
            if re.match(r"^\s*return\b", l):
                returns += 1
        if length > 30 or returns > 4:
            return _fail(
                "warn",
                "function %r too complex (length=%d, returns=%d)"
                % (m.group(1), length, returns),
            )
    return _ok()


def hallucinated_api(name, code, context):
    known = set((context or {}).get("known_apis", ()))
    used = {m.group(1) for m in _RE_ATTR.finditer(code)}
    used |= {m.group(1) for m in _RE_ACCESS.finditer(code)}
    used -= _SAFE_ATTRS
    unknown = sorted(used - known)
    if unknown:
        return _fail(
            "blocker",
            "attribute call(s) not in known_apis allowlist "
            "(possible hallucinated API): %s" % ", ".join(unknown[:8]),
        )
    return _ok()


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


def run_gauntlet(files, context=None):
    context = dict(context or {})
    context["files"] = files
    findings = []
    for fn, severity in CHECKLIST:
        if fn is has_tests:
            r = fn("<changeset>", "", context)
            if not r.passed:
                findings.append(
                    {"file": "<changeset>", "check": fn.__name__,
                     "severity": severity, "note": r.note}
                )
            continue
        for path, code in files.items():
            r = fn(path, code, context)
            if not r.passed:
                findings.append(
                    {"file": path, "check": fn.__name__,
                     "severity": severity, "note": r.note}
                )
    passed = not any(f["severity"] == "blocker" for f in findings)
    return {"passed": passed, "findings": findings}
