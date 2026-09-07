"""Probe: test fetching one post's detail. Tries the mobile API
/api/v1/media/{id}/info/ first; if that 400s, falls back to loading the post
page and sniffing its GraphQL (PolarisPostActionLoadPostQuery etc).
"""
from __future__ import annotations

import json
import sys
import time

sys.path.insert(0, __file__.rsplit("\\", 1)[0])
import common

CODE = "Dbaan1SE_zu"


def main():
    pw, ctx = common.launch()
    try:
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto("https://www.instagram.com/", wait_until="domcontentloaded")
        time.sleep(3)
        # try 1: mobile api
        try:
            mid = common.short_to_media_id(CODE)
            data = common.api_fetch(page, f"/api/v1/media/{mid}/info/")
            print("MOBILE_API OK, keys:", list(data.keys())[:5])
            return
        except Exception as e:
            print("mobile api failed:", str(e)[:100])
        # try 2: drive the post page and sniff
        got = []

        def on_resp(resp):
            try:
                if "graphql" in resp.url or "api/v1" in resp.url:
                    got.append(resp)
            except Exception:
                pass

        page.on("response", on_resp)
        page.goto(f"https://www.instagram.com/p/{CODE}/", wait_until="domcontentloaded")
        time.sleep(8)
        print(f"captured {len(got)} api responses")
        for r in got[:10]:
            try:
                body = json.loads(r.body().decode("utf-8", "ignore"))
                txt = json.dumps(body)
                if '"shortcode"' in txt or CODE in txt:
                    print("HIT:", r.url[:110])
                    # where does post data live?
                    if "items" in body:
                        print("  shape: api items")
                    if "data" in body:
                        print("  shape: graphql data")
            except Exception:
                continue
    finally:
        try:
            ctx.close()
        except Exception:
            pass
        pw.stop()


if __name__ == "__main__":
    main()
