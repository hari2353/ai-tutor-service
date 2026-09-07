"""Phase 1: log in once, find username, build the saved-posts index.

Run:  python scripts/ig_crawler/run.py login
"""
from __future__ import annotations

import sys
import time

sys.path.insert(0, __file__.rsplit("\\", 1)[0])

import common


def main() -> None:
    pw, ctx = common.launch()
    try:
        page = ctx.new_page()
        page.goto("https://www.instagram.com/", wait_until="domcontentloaded")
        print("BROWSER OPEN - log in if prompted (up to 10 min)...", flush=True)
        if not common.wait_for_login(ctx, 600):
            print("NOT_LOGGED_IN: run again and complete the login")
            return
        print("Logged in. Detecting username...", flush=True)
        st = common.load_state()
        user = common.detect_username(page)
        st["username"] = user or st["username"]
        common.save_state(st)
        print(f"USERNAME={st['username']}")
        print("OK - session cookies persisted in profile; close browser when ready")
    finally:
        time.sleep(2)
        ctx.close()
        pw.stop()


if __name__ == "__main__":
    main()
