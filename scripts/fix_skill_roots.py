#!/usr/bin/env python3
"""One-time fix: every /tutor-* skill hardcoded one absolute path
(`C:\\Users\\medic\\OneDrive\\Documents\\ai-tutor-service`) as the repo root.
That directory does not exist on this machine, and tutor-start's own rule is
"if it does not exist, say so and stop" — so all twelve skills were dead on
arrival after the repo moved. Root discovery must be structural, not a frozen
path: find the directory that contains CONTENT-STATUS.md, walking up from the
current working directory. Idempotent."""
from __future__ import annotations

import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent

OLD_LINE = "**Repo root** (`$ROOT`): `C:\\Users\\medic\\OneDrive\\Documents\\ai-tutor-service`"
OLD_STOP = "If that directory does not exist, say so and stop. Do not guess another path."
NEW_ROOT = (
    "**Repo root** (`$ROOT`): the directory containing `CONTENT-STATUS.md`. "
    "Find it by walking up from your current working directory until that file appears; "
    "if you never find it, ask the user where the repo lives — do not guess a path."
)

changed = []
for md in sorted((ROOT / "skills").glob("*/SKILL.md")):
    txt = md.read_text(encoding="utf-8")
    orig = txt
    txt = txt.replace(OLD_LINE, NEW_ROOT)
    txt = txt.replace(OLD_STOP + "\n", "")
    txt = txt.replace(OLD_STOP, "")
    txt = txt.replace(
        'node app/tests/dom.test.js "C:\\Users\\medic\\OneDrive\\Documents\\ai-tutor-service"',
        'node app/tests/dom.test.js "$ROOT"')
    if txt != orig:
        md.write_text(txt, encoding="utf-8")
        changed.append(md.parent.name)

readme = ROOT / "README.md"
txt = readme.read_text(encoding="utf-8")
if "medic" in txt:
    txt = txt.replace(
        "```\nC:\\Users\\medic\\OneDrive\\Documents\\ai-tutor-service\\app\\index.html\n```",
        "```\n<repo-root>\\app\\index.html\n```")
    readme.write_text(txt, encoding="utf-8")
    changed.append("README.md")

spec = ROOT / "templates" / "MODULE-SPEC.md"
txt = spec.read_text(encoding="utf-8")
if "medic" in txt:
    txt = txt.replace(
        "All paths below are relative to the repo root, "
        "`C:\\Users\\medic\\OneDrive\\Documents\\ai-tutor-service`.",
        "All paths below are relative to the repo root "
        "(the directory containing `CONTENT-STATUS.md`).")
    spec.write_text(txt, encoding="utf-8")
    changed.append("templates/MODULE-SPEC.md")

print("changed:", ", ".join(changed) if changed else "(nothing)")

left = 0
OLD_PATH = "C:\\Users\\medic\\OneDrive\\Documents\\ai-tutor-service"
for p in ROOT.rglob("*.md"):
    if ".git" in p.parts:
        continue
    if OLD_PATH in p.read_text(encoding="utf-8"):
        print("STILL CONTAINS PATH:", p)
        left += 1
print("files still containing old path:", left)
raise SystemExit(1 if left else 0)
