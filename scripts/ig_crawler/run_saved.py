"""Phase 2 v2: harvest saved posts by driving the real /saved/ page and
capturing the GraphQL responses the page itself makes while scrolling.

No forged requests: the app does the talking, we just listen. Resumable;
re-run until DONE.
"""
from __future__ import annotations

import json
import sys
import time

sys.path.insert(0, __file__.rsplit("\\", 1)[0])

import common
import normalize


def collect_anchors(page) -> set:
    try:
        hrefs = page.eval_on_selector_all(
            'a[href*="/p/"], a[href*="/reel/"]', "els => els.map(e => e.href)")
        return {common.SHORT_RE.search(h).group(1) for h in hrefs
                if common.SHORT_RE.search(h)}
    except Exception:
        return set()


def main() -> None:
    st = common.load_state()
    user = st.get("username")
    if not user:
        print("NO_USERNAME: run run_login.py first")
        return
    pw, ctx = common.launch()
    responses = []

    def on_response(resp):
        try:
            if "graphql" in resp.url and resp.request.method == "POST":
                responses.append(resp)
        except Exception:
            pass

    try:
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.on("response", on_response)
        page.goto(f"https://www.instagram.com/{user}/saved/all-posts/",
                  wait_until="domcontentloaded")
        time.sleep(6)
        if not common.is_logged_in(ctx):
            print("NOT_LOGGED_IN: run run_login.py first")
            return

        known: set = set(st["records"].keys())
        anchors = collect_anchors(page)
        known |= anchors
        stable, rounds = 0, 0
        budget_end = time.time() + 95
        while time.time() < budget_end and stable < 4 and rounds < 60:
            rounds += 1
            try:
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            except Exception:
                pass
            time.sleep(2.2)
            # drain captured graphql responses
            new_recs = 0
            while responses:
                resp = responses.pop(0)
                try:
                    body = json.loads(resp.body().decode("utf-8", "ignore"))
                except Exception:
                    continue
                for rec in normalize.extract_posts(body, "saved"):
                    code = rec["shortcode"]
                    if code and code not in st["records"]:
                        rec["via"] = "graphql"
                        st["records"][code] = rec
                        st["queue"].append(code)
                        new_recs += 1
                # saved-tab responses may nest under xdt_api__graphql__saved...
                try:
                    text = json.dumps(body)
                except Exception:
                    text = ""
                if new_recs:
                    common.save_state(st)
            anchors = collect_anchors(page) | anchors
            new_anchors = anchors - known
            known |= anchors
            # link anchors to records via shortcode-only entries (detail phase fills them)
            for code in new_anchors:
                st["queue"].append(code)
                st["records"].setdefault(code, {
                    "shortcode": code, "source": "saved", "items": [],
                    "creator_username": "", "caption": "", "via": "anchor"})
            if new_recs == 0 and not new_anchors:
                stable += 1
            else:
                stable = 0
                print(f"  round {rounds}: +{new_recs} graphql recs, "
                      f"grid now {len(anchors)}", flush=True)
        # final drain
        while responses:
            resp = responses.pop(0)
            try:
                body = json.loads(resp.body().decode("utf-8", "ignore"))
                for rec in normalize.extract_posts(body, "saved"):
                    code = rec["shortcode"]
                    if code and code not in st["records"]:
                        rec["via"] = "graphql"
                        st["records"][code] = rec
                        st["queue"].append(code)
            except Exception:
                continue
        st["stats"]["saved_rounds"] = rounds
        st["stats"]["saved_grid_size"] = len(anchors)
        if stable >= 4:
            st["phase_saved_done"] = True
            print(f"DONE: saved page exhausted ({len(st['records'])} records, "
                  f"{len(anchors)} grid anchors)", flush=True)
        else:
            print(f"TIME_BUDGET: {len(st['records'])} records so far; "
                  f"re-run to continue", flush=True)
        common.save_state(st)
    finally:
        try:
            ctx.close()
        except Exception:
            pass
        pw.stop()


if __name__ == "__main__":
    main()
