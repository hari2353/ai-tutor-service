"""Phase 7: OCR every downloaded image and video frame with Windows OCR
(winocr wraps the built-in Windows.Media.Ocr engine - no install beyond the
pip package, good accuracy on slide/text screenshots).

Writes mining/posts/<code>/ocr.txt with all slides' text. Resumable: skips
posts that already have a non-empty ocr.txt.

Run:  python scripts/ig_crawler/run_ocr.py
"""
from __future__ import annotations

import asyncio
import pathlib
import sys
import time

sys.path.insert(0, __file__.rsplit("\\", 1)[0])

import common

import winocr
from PIL import Image

MIN_TEXT = 12          # chars; below this treat as empty (blank frame)
CONCURRENCY = 4


async def ocr_one(path: pathlib.Path, sem: asyncio.Semaphore) -> str:
    async with sem:
        try:
            img = Image.open(path)
            if img.mode != "RGB":
                img = img.convert("RGB")
            r = await winocr.recognize_pil(img)
            return (r.text or "").strip()
        except Exception as e:
            return f"[ocr failed: {str(e)[:60]}]"


async def ocr_post_dir(d: pathlib.Path, sem: asyncio.Semaphore) -> str:
    """OCR all slides of one post, in slide order, into ocr.txt."""
    files = sorted(
        [f for f in d.glob("i*.jpg") if not f.name.endswith(".part")]
        + list(d.glob("v*_frame_*.jpg")),
        key=lambda f: (f.name[0], int("".join(ch for ch in f.name if ch.isdigit()) or 0)),
    )
    parts = []
    for f in files:
        text = await ocr_one(f, sem)
        if text and len(text) >= MIN_TEXT:
            parts.append(f"----- {f.name} -----\n{text}")
    return "\n\n".join(parts)


def main() -> None:
    posts_dir = common.POSTS
    todo = []
    for d in posts_dir.iterdir():
        if not d.is_dir():
            continue
        ocr_p = d / "ocr.txt"
        if ocr_p.exists() and ocr_p.stat().st_size > 0:
            continue
        has_media = any(d.glob("i*.jpg")) or any(d.glob("v*_frame_*.jpg"))
        if has_media:
            todo.append(d)
    print(f"posts to OCR: {len(todo)}", flush=True)
    if not todo:
        print("DONE: nothing to OCR")
        return
    budget_end = time.time() + 480
    sem = asyncio.Semaphore(CONCURRENCY)
    loop = asyncio.new_event_loop()
    done = 0
    for d in todo:
        if time.time() > budget_end:
            print(f"TIME_BUDGET - {done}/{len(todo)} this run; re-run to continue", flush=True)
            return
        try:
            text = loop.run_until_complete(ocr_post_dir(d, sem))
            (d / "ocr.txt").write_text(text or "[no text detected]", encoding="utf-8")
            done += 1
            if done % 25 == 0:
                print(f"  {done}/{len(todo)}...", flush=True)
        except Exception as e:
            (d / "ocr.txt").write_text(f"[ocr failed: {str(e)[:80]}]", encoding="utf-8")
    print(f"DONE: OCR complete for {done} posts", flush=True)


if __name__ == "__main__":
    main()
