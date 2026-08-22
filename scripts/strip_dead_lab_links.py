#!/usr/bin/env python3
"""One-time honesty fix: curriculum modules referenced labs that were never built.

285 of 289 `labs/<lang>/<slug>/` references pointed at directories that do not
exist. A module that promises a lab it cannot deliver fails the repo's own rule
("a module isn't done until its lab tests pass") in a quieter, worse way: the
claim is simply false. This script removes the false claims:

- a `> **Lab:** ...` header line whose target dir is missing -> line deleted
- any other inline `labs/x/y/` mention whose target dir is missing ->
  replaced with `(lab pending)`

References to labs that DO exist (currently labs/py/01-circuit-breaker) are kept.
Idempotent: run again and nothing changes. Kept under scripts/ so the change is
auditable rather than magic.
"""
from __future__ import annotations

import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
LAB_RE = re.compile(r"labs/([a-z]+)/([0-9a-z\-]+)/")
HEADER_LINE = re.compile(r"^> \*\*Lab:\*\*.*labs/.+$\n?", re.M)

removed_lines = 0
inline_fixed = 0
files_touched = 0

for md in sorted(ROOT.glob("curriculum/**/*.md")):
    txt = md.read_text(encoding="utf-8")
    orig = txt

    def missing(m: re.Match) -> bool:
        return not (ROOT / "labs" / m.group(1) / m.group(2)).is_dir()

    # 1. drop dead "> **Lab:**" header lines
    def drop_header(m: re.Match) -> str:
        global removed_lines
        hit = LAB_RE.search(m.group(0))
        if hit and missing(hit):
            removed_lines += 1
            return ""
        return m.group(0)

    txt = HEADER_LINE.sub(drop_header, txt)

    # 2. neutralise remaining inline mentions of labs that don't exist
    def fix_inline(m: re.Match) -> str:
        global inline_fixed
        if missing(m):
            inline_fixed += 1
            return "(lab pending)"
        return m.group(0)

    txt = LAB_RE.sub(fix_inline, txt)

    if txt != orig:
        md.write_text(txt, encoding="utf-8")
        files_touched += 1

print(f"files touched: {files_touched}")
print(f"dead 'Lab:' header lines removed: {removed_lines}")
print(f"inline dead references marked '(lab pending)': {inline_fixed}")

# verify nothing dead remains anywhere
left = 0
for md in ROOT.glob("curriculum/**/*.md"):
    for m in LAB_RE.finditer(md.read_text(encoding="utf-8")):
        if not (ROOT / "labs" / m.group(1) / m.group(2)).is_dir():
            left += 1
print(f"dead references remaining: {left}")
raise SystemExit(1 if left else 0)
