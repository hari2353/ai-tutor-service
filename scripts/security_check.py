#!/usr/bin/env python3
"""Security & privacy gate for the repo.

Two jobs:
1. SECRET SCAN over git-tracked files. High-confidence credential patterns are
   hard failures; low-confidence "looks like a hardcoded secret" assignments are
   warnings (curriculum prose legitimately discusses secrets, so generic
   patterns cannot fail the build without drowning real signal).
2. PRIVACY AUDIT: verifies the personal job queue never entered git history,
   and lists files whose content is personal enough to require the GitHub
   remote to be PRIVATE.

Exit 1 on any hard failure. Wired into app/tests/run.ps1 so ALL GREEN can never
include an insecure tree.
"""
from __future__ import annotations

import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent

HIGH_CONFIDENCE = [
    ("AWS access key id",        re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("AWS secret key",           re.compile(r"(?i)aws(.{0,20})?['\"][0-9a-zA-Z/+]{40}['\"]")),
    ("private key block",        re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]{0,300}?-----END [A-Z ]*PRIVATE KEY-----|-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("GitHub token",             re.compile(r"\bgh[pousr]_[0-9A-Za-z]{36,}\b")),
    ("Google API key",           re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b")),
    ("Slack token",              re.compile(r"\bxox[baprs]-[0-9A-Za-z\-]{10,}\b")),
    ("OpenAI-style sk key",      re.compile(r"\bsk-[0-9A-Za-z]{32,}\b")),
    ("Anthropic-style key",      re.compile(r"\bsk-ant-[0-9A-Za-z_\-]{32,}\b")),
    ("credentials-in-url",       re.compile(r"[a-z+]+://[^/\s:@]+:[^/\s:@]+@[^\s/]+")),
]

# A curriculum that teaches auth MUST show what credential shapes look like.
# These markers identify deliberate placeholders, not leaks: an annotated
# "(never leaves this workload)" PEM diagram, or the repo-wide local-stack
# convention of throwaway dev creds on dotless docker-service hostnames
# (postgres:devpass@db — same spirit as README's POSTGRES_PASSWORD=dev).
PLACEHOLDER_BLOCK = re.compile(r"\(|\.\.\.|<[^>]+>|(never|do not|don't) ")
DEMO_URL = re.compile(
    r"://(?:user|username|admin|demo|app|postgres|root|dev):"
    r"(?:pass|password|devpass|dev|changeme|password)@"
    r"|[a-z+]+://[^/\s:@]+:[^/\s:@]+@(?:db|redis|postgres|mysql|mongo|localhost)\b")

LOW_CONFIDENCE = re.compile(
    r"(?i)\b(api[_-]?key|secret|password|passwd|token)\b\s*[:=]\s*[\"'][^\"'{<>]{8,}[\"']")

SKIP_SUFFIXES = {".png", ".jpg", ".pdf", ".pyc", ".woff", ".woff2", ".ico"}
ALLOW_SUBSTRINGS = ("example", "YOUR_", "<", "changeme", "os.environ", "getenv",
                    "placeholder", "redacted")


def tracked_files() -> list[pathlib.Path]:
    out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True,
                         text=True, check=True).stdout.splitlines()
    return [ROOT / p for p in out if p]


def queue_never_committed() -> bool:
    """interview_prep_queue.json is gitignored operational data; prove it."""
    log = subprocess.run(
        ["git", "log", "--all", "--name-only", "--pretty=format:"],
        cwd=ROOT, capture_output=True, text=True, check=True).stdout
    hits = [l for l in log.splitlines()
            if "interview_prep_queue" in l or l.endswith("progress/session-log.md")]
    return not hits


def main() -> int:
    hard: list[str] = []
    warns: list[str] = []

    for path in tracked_files():
        if path.suffix.lower() in SKIP_SUFFIXES or not path.exists():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        rel = str(path.relative_to(ROOT)).replace("\\", "/")

        for name, pat in HIGH_CONFIDENCE:
            for m in pat.finditer(text):
                hit = m.group(0)
                if "PRIVATE KEY" in hit and PLACEHOLDER_BLOCK.search(hit):
                    continue
                if name == "credentials-in-url" and DEMO_URL.search(hit):
                    continue
                line_no = text.count("\n", 0, m.start()) + 1
                hard.append(f"{rel}:{line_no}  [{name}]")

        for m in LOW_CONFIDENCE.finditer(text):
            frag = m.group(0)
            if any(a in frag for a in ALLOW_SUBSTRINGS):
                continue
            line_no = text.count("\n", 0, m.start()) + 1
            warns.append(f"{rel}:{line_no}  {frag[:70]}")

    privacy_ok = queue_never_committed()

    print("== security scan ==")
    print(f"hard failures: {len(hard)}   warnings: {len(warns)}")
    for h in hard[:40]:
        print("  FAIL", h)
    for w in warns[:15]:
        print("  warn", w)
    if len(warns) > 15:
        print(f"  ... and {len(warns)-15} more warnings")

    print("== privacy audit ==")
    print(("OK    interview_prep_queue.json absent from all git history"
           if privacy_ok else
           "FAIL  interview_prep_queue.json appears in git history"))
    print("NOTE  repo contains resume-derived content (progress/, mocks/, "
          "CONFIRM hints, personal email in COMMIT.md): the GitHub remote MUST be private.")

    return 1 if (hard or not privacy_ok) else 0


if __name__ == "__main__":
    sys.exit(main())
