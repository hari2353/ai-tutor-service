"""Phase 5: download media for every record (images, carousel frames, video
mp4), then extract 5 frames per video via ffmpeg. Resumable; skip files that
already exist. Uses requests with the browser's cookies for CDN auth.

Run:  python scripts/ig_crawler/run_media.py
"""
from __future__ import annotations

import pathlib
import subprocess
import sys
import time

sys.path.insert(0, __file__.rsplit("\\", 1)[0])

import common
import json
import requests

FRAME_PCTS = (0.08, 0.30, 0.50, 0.70, 0.92)


def media_dir(code: str) -> pathlib.Path:
    d = common.POSTS / code
    d.mkdir(parents=True, exist_ok=True)
    return d


def download(url: str, dest: pathlib.Path, s) -> bool:
    if dest.exists() and dest.stat().st_size > 1024:
        return True
    try:
        r = s.get(url, timeout=30, stream=True)
        if r.status_code != 200:
            return False
        tmp = dest.with_suffix(".part")
        with open(tmp, "wb") as f:
            for chunk in r.iter_content(8192):
                f.write(chunk)
        tmp.replace(dest)
        return True
    except Exception:
        if dest.with_suffix(".part").exists():
            try:
                dest.with_suffix(".part").unlink()
            except Exception:
                pass
        return False


def extract_frames(mp4: pathlib.Path, out_prefix: pathlib.Path):
    if not mp4.exists() or mp4.stat().st_size < 1024:
        return False
    # skip if frames already present
    if any(out_prefix.parent.glob(out_prefix.name + "*.jpg")):
        return True
    dur = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(mp4)],
        capture_output=True, text=True).stdout.strip()
    try:
        dur = float(dur)
    except ValueError:
        dur = 0
    marks = [f"{dur * p:.2f}" for p in FRAME_PCTS] if dur > 0 else ["1"]
    ok = 0
    for i, t in enumerate(marks):
        out = out_prefix.with_name(f"{out_prefix.name}_{i}.jpg")
        r = subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-ss", t, "-i", str(mp4),
             "-frames:v", "1", "-q:v", "3", str(out)],
            capture_output=True, text=True)
        if r.returncode == 0 and out.exists():
            ok += 1
    return ok > 0


def main() -> None:
    st = common.load_state()
    records = st["records"]
    # useful-only: same classifier as run_enrich; skip noise posts
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
    import run_enrich
    useful = set()
    for code, rec in records.items():
        score, _ = run_enrich.classify(rec.get("caption", ""), rec.get("creator_username", ""))
        if score >= 2:
            useful.add(code)
    codes = [c for c in useful if records[c].get("source") == "saved"]
    codes += [c for c in useful if records[c].get("source") != "saved"]
    # hard cap: total media-fetching posts per run-batch to bound disk/time;
    # saved-first ordering means the important ones are always done first
    codes = codes[:3000]
    print(f"useful posts: {len(useful)} (of {len(records)} records); downloading for {len(codes)}", flush=True)
    s = requests.Session()
    s.headers.update({"User-Agent": common.UA})
    budget_end = time.time() + 480
    done = 0
    for code in codes:
        if time.time() > budget_end:
            print(f"TIME_BUDGET - {done} records processed this run; re-run to continue", flush=True)
            return
        rec = records[code]
        d = media_dir(code)
        meta_p = d / "meta.json"
        if not meta_p.exists():
            meta_p.write_text(json.dumps(rec, indent=2, ensure_ascii=False), encoding="utf-8")
        items = rec.get("items", [])
        if not items and not (d / "NO_MEDIA.txt").exists():
            (d / "NO_MEDIA.txt").write_text("no media urls in record", encoding="utf-8")
        for idx, it in enumerate(items):
            url = it.get("url") or ""
            if not url:
                continue
            kind = it.get("kind")
            if kind == "video":
                v = d / f"v{idx}.mp4"
                if download(url, v, s):
                    extract_frames(v, d / f"v{idx}_frame")
            else:
                p = d / f"i{idx}.jpg"
                if not download(url, p, s):
                    fail = d / f"i{idx}.failed"
                    if not fail.exists():
                        fail.write_text(url, encoding="utf-8")
        done += 1
    print(f"DONE: media handled for {len(codes)} records", flush=True)


if __name__ == "__main__":
    main()
