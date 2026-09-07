"""Media download, prioritized: representative posts of unique TOPICS (not
every post). Reads mining/topics.json, orders gap topics by frequency (the
crowd-vote signal), and downloads media for each topic's representative
post (+ up to 2 alternates). Also downloads any saved post not yet done.

Run:  python scripts/ig_crawler/run_topic_media.py
"""
from __future__ import annotations

import json
import pathlib
import sys
import time

sys.path.insert(0, __file__.rsplit("\\", 1)[0])
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import common
import requests

from run_media import download, extract_frames, media_dir


def main() -> None:
    st = common.load_state()
    records = st["records"]
    topics = json.loads((common.MINE / "topics.json").read_text(encoding="utf-8"))["topics"]
    gaps = [t for t in topics if t["gap_verdict"] == "GAP"]
    partials = [t for t in topics if t["gap_verdict"] == "partial"]
    gaps.sort(key=lambda t: -t["count"])
    partials.sort(key=lambda t: -t["count"])

    want: list[str] = []
    seen = set()
    for t in gaps[:1200] + partials[:600]:
        for code in [t["representative"]["shortcode"]] + t["members"][:2]:
            if code not in seen and code in records:
                seen.add(code)
                want.append(code)
    # saved posts always in
    for code, rec in records.items():
        if rec.get("source") == "saved" and code not in seen:
            seen.add(code)
            want.append(code)

    print(f"downloading media for {len(want)} prioritized posts "
          f"(top {min(len(gaps),1200)} gap reps + {min(len(partials),600)} partial reps + saved)",
          flush=True)
    s = requests.Session()
    s.headers.update({"User-Agent": common.UA})
    budget_end = time.time() + 480
    done = 0
    for code in want:
        if time.time() > budget_end:
            print(f"TIME_BUDGET - {done}/{len(want)} this run; re-run to continue", flush=True)
            return
        rec = records[code]
        d = media_dir(code)
        meta_p = d / "meta.json"
        if not meta_p.exists():
            meta_p.write_text(json.dumps(rec, indent=2, ensure_ascii=False), encoding="utf-8")
        for idx, it in enumerate(rec.get("items", [])):
            url = it.get("url") or ""
            if not url:
                continue
            if it.get("kind") == "video":
                v = d / f"v{idx}.mp4"
                if download(url, v, s):
                    extract_frames(v, d / f"v{idx}_frame")
            else:
                download(url, d / f"i{idx}.jpg", s)
        done += 1
    print(f"DONE: {done} prioritized posts have media", flush=True)


if __name__ == "__main__":
    main()
