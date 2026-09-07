"""Phase 3: for each queued shortcode, fetch full detail (carousel children,
video URLs, caption) and keep as records. Also extracts external links from
captions, and registers creators for phase 4.

Run:  python scripts/ig_crawler/run_detail.py
"""
from __future__ import annotations

import sys
import time

sys.path.insert(0, __file__.rsplit("\\", 1)[0])

import common
import normalize

EXT_LINK_RE = common.EXT_LINK_RE


def queue_links_in_caption(text: str) -> list[str]:
    # captions mention links but IG strips them; still capture raw text URLs
    return EXT_LINK_RE.findall(text or "")


def main() -> None:
    st = common.load_state()
    queue = [c for c in st["queue"] if not st["fetched"].get(c)]
    if not queue:
        print("DONE: detail queue empty")
        return
    budget_end = time.time() + 480
    pw, ctx = common.launch()
    made_progress = False
    try:
        page = ctx.new_page()
        page.goto("https://www.instagram.com/", wait_until="domcontentloaded")
        time.sleep(3)
        if not common.is_logged_in(ctx):
            print("NOT_LOGGED_IN: run run_login.py first")
            return
        while queue and time.time() < budget_end:
            code = queue.pop(0)
            if st["fetched"].get(code):
                continue
            try:
                media_id = common.short_to_media_id(code)
                data = common.api_fetch(page, f"/api/v1/media/{media_id}/info/")
                recs = normalize.extract_posts(data, st["records"].get(code, {}).get("source", "saved"))
                if not recs:
                    raise RuntimeError("no media in response")
                rec = max(recs, key=lambda r: len(r["items"]))
                rec["caption_links"] = queue_links_in_caption(rec.get("caption", ""))
                prev = st["records"].get(code, {})
                prev.update(rec)
                st["records"][code] = prev
                st["fetched"][code] = True
                made_progress = True
                # register creator
                cu = rec.get("creator_username")
                if cu and cu not in st["creators"]:
                    st["creators"][cu] = {
                        "id": rec.get("creator_id", ""),
                        "full_name": rec.get("creator_full_name", ""),
                        "scanned": False,
                        "next_max_id": None,
                    }
                    print(f"  +creator @{cu}", flush=True)
                print(f"  detail {code} ({len(rec['items'])} media) @{cu}", flush=True)
            except Exception as e:
                st["fetched"][code] = "failed"
                print(f"  fail {code}: {str(e)[:80]}", flush=True)
            common.save_state(st)
            common.nap(2.2, 4.8)
        print(
            f"{'TIME_BUDGET' if queue else 'DONE'} - fetched {len(st['fetched'])}/{len(st['queue'])}, "
            f"remaining {len(queue)}; re-run to continue" if queue else "DONE: all details fetched",
            flush=True,
        )
    finally:
        try:
            ctx.close()
        except Exception:
            pass
        pw.stop()
        common.save_state(st)


if __name__ == "__main__":
    main()
