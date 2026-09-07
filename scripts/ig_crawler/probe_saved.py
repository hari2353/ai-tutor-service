"""Probe: open instagram.com/<user>/saved/ and log every XHR the page itself
makes, to learn the exact endpoint+params Instagram's web app uses for saved
posts. Read-only, 40 seconds.
"""
from __future__ import annotations

import json
import sys
import time

sys.path.insert(0, __file__.rsplit("\\", 1)[0])
import common

hits = []


def on_response(resp):
    try:
        url = resp.url
        req = resp.request
        if req.resource_type in ("xhr", "fetch") and "instagram.com" in url:
            hits.append((url, dict(req.headers)))
    except Exception:
        pass


def main():
    pw, ctx = common.launch()
    try:
        page = ctx.new_page()
        page.on("response", on_response)
        page.goto("https://www.instagram.com/", wait_until="domcontentloaded")
        time.sleep(3)
        if not common.is_logged_in(ctx):
            print("NOT_LOGGED_IN")
            return
        st = common.load_state()
        user = st.get("username") or common.detect_username(page)
        print(f"user={user}", flush=True)
        page.goto(f"https://www.instagram.com/{user}/saved/", wait_until="domcontentloaded")
        time.sleep(8)
        # scroll a few times to trigger pagination requests
        for _ in range(3):
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(3)
        seen = set()
        for url, hdrs in hits:
            key = url.split("?")[0]
            if key in seen:
                continue
            if any(k in url for k in ("saved", "graphql", "api/v1")):
                seen.add(key)
                print("URL: " + url[:160])
                interesting = {k: v[:40] for k, v in hdrs.items()
                                if k.lower() in ("x-ig-app-id", "x-fb-friendly-name",
                                                  "x-requested-with", "content-type")}
                print("     headers: " + json.dumps(interesting))
    finally:
        try:
            ctx.close()
        except Exception:
            pass
        pw.stop()


if __name__ == "__main__":
    main()
