"""Probe v3: capture ALL xhr/fetch on the saved page with full post data and
response bodies, saved to a file for inspection.
"""
from __future__ import annotations

import json
import sys
import time

sys.path.insert(0, __file__.rsplit("\\", 1)[0])
import common

LOG = []


def on_request(req):
    try:
        if req.resource_type in ("xhr", "fetch"):
            LOG.append({
                "method": req.method,
                "url": req.url,
                "friendly": (req.headers or {}).get("x-fb-friendly-name", ""),
                "post_data": (req.post_data or "")[:2000],
            })
    except Exception:
        pass


def main():
    pw, ctx = common.launch()
    try:
        page = ctx.new_page()
        page.on("request", on_request)
        page.goto("https://www.instagram.com/", wait_until="domcontentloaded")
        time.sleep(2)
        st = common.load_state()
        user = st["username"]
        page.goto(f"https://www.instagram.com/{user}/saved/", wait_until="domcontentloaded")
        time.sleep(6)
        for _ in range(6):
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(2.5)
        out = common.MINE / "probe_requests.json"
        out.write_text(json.dumps(LOG, indent=2), encoding="utf-8")
        print(f"logged {len(LOG)} requests -> {out}")
    finally:
        try:
            ctx.close()
        except Exception:
            pass
        pw.stop()


if __name__ == "__main__":
    main()
