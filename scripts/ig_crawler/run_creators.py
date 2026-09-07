"""Phase 4: creator expansion. For each creator found in saved posts, page
through their feed via /api/v1/feed/user/{user_id}/ and collect post
records (same normalized shape). Educational filtering happens later in
the enrich phase; here we just collect everything with caps per creator.

Run:  python scripts/ig_crawler/run_creators.py
"""
from __future__ import annotations

import sys
import time

sys.path.insert(0, __file__.rsplit("\\", 1)[0])

import common
import normalize

# only expand creators that look educational (same classifier as enrich)
import run_enrich as _re

EXT_LINK_RE = common.EXT_LINK_RE

# safety cap: max posts to record per creator feed. "Exhaust everything"
# still needs a ceiling for one run; raise it and re-run to go deeper.
PER_CREATOR_CAP = 3000


def main() -> None:
    st = common.load_state()
    # educational creators only: >=2 saved posts classified useful, or any
    # saved post from them classified useful
    edu = set()
    for rec in st["records"].values():
        if rec.get("source") != "saved":
            continue
        score, _ = _re.classify(rec.get("caption", ""), rec.get("creator_username", ""))
        if score >= 2:
            edu.add(rec.get("creator_username"))
    # register any that detail-phase missed
    for u in edu:
        if u and u not in st["creators"]:
            st["creators"][u] = {"id": "", "full_name": "", "scanned": False,
                                 "next_max_id": None}
    st["stats"]["edu_creators"] = len(edu)
    pending = [u for u, c in st["creators"].items()
               if not c.get("scanned") and u in edu]
    print(f"educational creators: {len(edu)}; pending scan: {len(pending)}", flush=True)
    budget_end = time.time() + 1050
    pw, ctx = common.launch()
    try:
        page = ctx.new_page()
        page.goto("https://www.instagram.com/", wait_until="domcontentloaded")
        time.sleep(3)
        if not common.is_logged_in(ctx):
            print("NOT_LOGGED_IN: run run_login.py first")
            return
        while pending and time.time() < budget_end:
            uname = pending[0]
            cinfo = st["creators"][uname]
            uid = cinfo.get("id")
            if not uid:
                # resolve user id from username
                try:
                    u = common.api_fetch(page, f"/api/v1/users/web_profile_info/?username={uname}")
                    uid = (u.get("data") or {}).get("user", {}).get("id")
                    if not uid:
                        raise RuntimeError("no id")
                    cinfo["id"] = uid
                except Exception as e:
                    print(f"  @{uname}: resolve failed {str(e)[:60]}", flush=True)
                    cinfo["scanned"] = True
                    common.save_state(st)
                    pending.pop(0)
                    continue
            collected = cinfo.get("collected", 0)
            max_id = cinfo.get("next_max_id")
            progressed = False
            while time.time() < budget_end and collected < PER_CREATOR_CAP:
                path = f"/api/v1/feed/user/{uid}/?count=12" + (f"&max_id={max_id}" if max_id else "")
                try:
                    data = common.api_fetch(page, path)
                except Exception as e:
                    print(f"  @{uname}: feed fetch failed {str(e)[:60]}", flush=True)
                    time.sleep(4)
                    break
                progressed = True
                items = data.get("items") or []
                new = 0
                for it in items:
                    rec = normalize.normalize_post(it, f"creator:{uname}")
                    code = rec["shortcode"]
                    if code and code not in st["records"]:
                        rec["caption_links"] = EXT_LINK_RE.findall(rec.get("caption") or "")
                        st["records"][code] = rec
                        st["queue"].append(code)
                        # feed payloads already carry full media+caption: no
                        # detail refetch needed
                        st["fetched"][code] = True
                        new += 1
                collected += len(items)
                cinfo["collected"] = collected
                # advance pagination: update the local var, not just state
                max_id = data.get("next_max_id")
                cinfo["next_max_id"] = max_id
                common.save_state(st)
                print(f"  @{uname}: page +{new} new (total {collected})", flush=True)
                more = data.get("more_available")
                if not more or not max_id:
                    cinfo["scanned"] = True
                    cinfo["next_max_id"] = None
                    print(f"  @{uname}: DONE {collected} posts", flush=True)
                    break
                if collected >= PER_CREATOR_CAP:
                    print(f"  @{uname}: cap hit at {collected}; resumable next run", flush=True)
                    break
                common.nap(2.4, 5.2)
            if cinfo.get("scanned"):
                pending.pop(0)
            elif collected >= PER_CREATOR_CAP or not progressed:
                pending.pop(0)
            if not progressed and time.time() > budget_end:
                break
        left = len(pending)
        if left:
            print(f"TIME_BUDGET - {left} creators remaining; re-run to continue", flush=True)
        else:
            print("DONE: all creators scanned", flush=True)
    finally:
        try:
            ctx.close()
        except Exception:
            pass
        pw.stop()
        common.save_state(st)


if __name__ == "__main__":
    main()
