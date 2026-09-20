#!/usr/bin/env python3
"""Validate the authored curriculum contract against generated data and labs."""
from __future__ import annotations

import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
CURRICULUM = ROOT / "app" / "data" / "curriculum.json"
LAB_RE = re.compile(r"\*\*Lab:\*\*\s*`([^`]+)`")
ID_RE = re.compile(r"\*\*Module id:\*\*\s*`([^`]+)`")


def find_module_file(track_dir: str, module_id: str, slug: str, order: int) -> pathlib.Path | None:
    directory = ROOT / track_dir
    prefix = f"{order + 1:02d}-"
    by_id = []
    for path in directory.glob("*.md"):
        match = ID_RE.search(path.read_text(encoding="utf-8"))
        if match and match.group(1) == module_id:
            by_id.append(path)
    if len(by_id) == 1:
        return by_id[0]
    matches = [p for p in directory.glob("*.md")
               if p.stem.endswith(slug) or p.stem.startswith(prefix)]
    return matches[0] if len(matches) == 1 else None


def main() -> int:
    data = json.loads(CURRICULUM.read_text(encoding="utf-8"))
    errors: list[str] = []
    tracks = {t["id"]: t for t in data["tracks"]}
    modules = [m | {"track_id": t["id"], "track_dir": t["dir"]}
               for t in data["tracks"] for m in t["modules"]]
    module_ids = {m["id"] for m in modules}

    for track in data["tracks"]:
        for prereq in track.get("prereqs", []):
            if prereq not in tracks:
                errors.append(f"track {track['id']} has unknown prerequisite {prereq}")

    for module in modules:
        path = find_module_file(module["track_dir"], module["id"], module["slug"], module["order"])
        if path is None:
            errors.append(f"{module['id']} has no unique curriculum markdown file")
            continue
        text = path.read_text(encoding="utf-8")
        match = ID_RE.search(text)
        if not match or match.group(1) != module["id"]:
            errors.append(f"{module['id']} metadata id mismatch in {path.relative_to(ROOT)}")
        for lab in LAB_RE.findall(text):
            target = ROOT / lab.rstrip("/")
            required = ("README.md", "PRODUCTION.md", "starter", "solution", "tests")
            missing = [name for name in required if not (target / name).exists()]
            if missing:
                errors.append(f"{module['id']} lab {lab} missing {', '.join(missing)}")
        if "sprint" in module.get("tags", []):
            for kind, directory in (("cards", "cards"), ("drills", "drillsets")):
                fragment = ROOT / "app" / "data" / directory / f"{module['id']}.json"
                if not fragment.exists():
                    errors.append(f"sprint module {module['id']} missing {kind} fragment")

    for kind, directory in (("cards", "cards"), ("drills", "drillsets")):
        for fragment in (ROOT / "app" / "data" / directory).glob("*.json"):
            payload = json.loads(fragment.read_text(encoding="utf-8"))
            for row in payload.get(kind, []):
                module = row.get("module") or fragment.stem
                if module not in module_ids:
                    errors.append(f"{fragment.relative_to(ROOT)} row {row.get('id')} references unknown {module}")

    if errors:
        print(f"content audit: {len(errors)} failure(s)")
        print("\n".join(f"  FAIL {e}" for e in errors))
        return 1
    print(f"content audit: OK ({len(modules)} modules, {len(tracks)} tracks)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
