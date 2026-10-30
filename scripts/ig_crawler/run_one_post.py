"""Fetch detail for specific post shortcodes (no saved-index needed).

Run:  python scripts/ig_crawler/run_one_post.py CODE1 CODE2 ...
Prints creator, caption, links, OCR'd slide text, and item URLs per post.
Images land in mining/posts/<code>/ for reuse (run_ocr_mac.py backfills).
"""
from __future__ import annotations

import pathlib
import sys
import time
import urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import common
import normalize
import run_ocr_mac

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15"


def download(url: str, dest: pathlib.Path) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r, open(dest, "wb") as f:
        f.write(r.read())


def dump(rec: dict, code: str) -> None:
    print(f"=== {code} ===")
    print("creator:", rec.get("creator_username"))
    print("caption:", (rec.get("caption") or "")[:2200])
    pd = common.POSTS / code
    pd.mkdir(parents=True, exist_ok=True)
    for i, it in enumerate(rec.get("items", [])[:10]):
        print(f"item {i}: {it.get('kind')} {it.get('url') or ''[:120]}")
        if it.get("kind") == "image" and it.get("url"):
            dest = pd / f"i{i}.jpg"
            try:
                if not dest.exists():
                    download(it["url"], dest)
            except Exception as e:
                print(f"  download failed: {str(e)[:80]}")
    text = run_ocr_mac.ocr_post_dir(pd)
    print("slides OCR:")
    print(text or "(no OCR text)")


def main() -> None:
    codes = [c for c in sys.argv[1:] if c]
    if not codes:
        print("usage: run_one_post.py SHORTCODE [SHORTCODE ...]")
        return
    pw, ctx = common.launch()
    try:
        page = ctx.new_page()
        page.goto("https://www.instagram.com/", wait_until="domcontentloaded")
        time.sleep(3)
        if not common.is_logged_in(ctx):
            print("NOT_LOGGED_IN: run run_login.py first")
            return
        for code in codes:
            try:
                mid = common.short_to_media_id(code)
                data = common.api_fetch(page, f"/api/v1/media/{mid}/info/")
                recs = normalize.extract_posts(data, "manual")
                if not recs:
                    raise RuntimeError("no media in response")
                dump(max(recs, key=lambda r: len(r["items"])), code)
            except Exception as e:
                print(f"=== {code} FAILED: {str(e)[:140]} ===")
            common.nap(3.0, 7.0)
    finally:
        time.sleep(1)
        ctx.close()
        pw.stop()


if __name__ == "__main__":
    main()
