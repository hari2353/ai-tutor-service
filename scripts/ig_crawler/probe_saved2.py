"""Probe v2: open the saved page, scroll hard, and capture the FIRST full
request details (url + post body + response json) for the request that
returns saved posts. Saves it for building the real harvester.
"""
from __future__ import annotations

import json
import sys
import time

sys.path.insert(0, __file__.rsplit("\\", 1)[0])
import common

captured = []


def on_request(req):
    try:
        u = req.url
        if ("graphql" in u) and req.method == "POST":
            captured.append(req)
    except Exception:
        pass


def main():
    pw, ctx = common.launch()
    try:
        page = ctx.new_page()
        page.on("request", on_request)
        page.goto("https://www.instagram.com/", wait_until="domcontentloaded")
        time.sleep(3)
        st = common.load_state()
        user = st.get("username")
        page.goto(f"https://www.instagram.com/{user}/saved/", wait_until="domcontentloaded")
        time.sleep(6)
        for _ in range(6):
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(2.5)
        print(f"captured {len(captured)} graphql POSTs", flush=True)
        for req in captured[:6]:
            body = req.post_data or ""
            friendly = (req.headers or {}).get("x-fb-friendly-name", "")
            if "saved" in body.lower() or "saved" in friendly.lower() or len(captured) <= 6:
                try:
                    resp = req.response()
                    rtext = resp.text()[:400] if resp else ""
                except Exception:
                    rtext = ""
                print("== friendly:", friendly)
                print("   url:", req.url[:120])
                print("   body:", body[:300])
                print("   resp:", rtext[:300])
                print()
    finally:
        try:
            ctx.close()
        except Exception:
            pass
        pw.stop()


if __name__ == "__main__":
    main()
