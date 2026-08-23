#!/usr/bin/env python3
"""Generate cheatsheets/ from written modules' `## Cheat card` sections.

The sprint modules already end in a one-screen cheat card (the house format
requires it) — so the "morning of the interview" folder can be assembled
mechanically instead of sitting at zero waiting for an LLM pass. Extracts each
sprint module's cheat card into cheatsheets/<NN>-<slug>.md plus a README index,
ordered by sprint weekend.

Re-run any time: idempotent, regenerates the whole folder."""
from __future__ import annotations

import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "cheatsheets"

CARD = re.compile(r"##\s*Cheat card\s*\n(.*?)(?=\n##\s|\Z)", re.S)


def module_file(track_dir: str, slug: str) -> pathlib.Path | None:
    for p in pathlib.Path(ROOT / track_dir).glob("*.md"):
        if p.stem.endswith(slug):
            return p
    return None


def main() -> None:
    cur = json.loads((ROOT / "app/data/curriculum.json").read_text(encoding="utf-8"))
    by_id = {m["id"]: m for t in cur["tracks"] for m in t["modules"]}
    dirs = {t["id"]: t["dir"] for t in cur["tracks"]}

    sprint_ids = [m["id"] for m in by_id.values() if "sprint" in m.get("tags", [])]
    sprint_ids.sort(key=lambda mid: by_id[mid].get("sprint_order", 999))

    OUT.mkdir(exist_ok=True)
    index = [
        "# Cheatsheets — the morning of",
        "",
        f"> Auto-generated from the sprint modules' `## Cheat card` sections by "
        f"`scripts/gen_cheatsheets.py` · {len(sprint_ids)} sheets · regenerate after content edits.",
        "",
        "| WE | Sheet | Module |",
        "|---|---|---|",
    ]
    made = 0
    for mid in sprint_ids:
        m = by_id[mid]
        src = module_file(dirs[mid.split("-")[0]], m["slug"])
        if src is None:
            continue
        txt = src.read_text(encoding="utf-8")
        hit = CARD.search(txt)
        if not hit:
            continue
        body = hit.group(1).strip()
        week = m.get("sprint_week", "?")
        out_name = f"we{int(week):02d}-{m['slug']}.md"
        (OUT / out_name).write_text(
            f"# {m['title']}\n\n> Sprint weekend {week} · source: `{src.relative_to(ROOT).as_posix()}`\n\n"
            + body + "\n",
            encoding="utf-8")
        index.append(f"| {week} | [{out_name}]({out_name}) | `{mid}` |")
        made += 1

    (OUT / "README.md").write_text("\n".join(index) + "\n", encoding="utf-8")
    print(f"cheatsheets: wrote {made} sheets + README.md into cheatsheets/")


if __name__ == "__main__":
    main()
