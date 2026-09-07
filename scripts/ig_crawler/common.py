"""Shared plumbing for the Instagram crawl phases.

Budget-driven, checkpointed after every unit of work, so a run killed by a
tool timeout can be re-run until it prints DONE. All IG data comes from the
page's own network responses or the logged-in fetch context. Delays
everywhere: this drives a real logged-in session and must look like a slow
human. mining/crawl_state/ holds live session cookies -- never commit it.
"""
from __future__ import annotations

import json
import pathlib
import random
import re
import time

ROOT = pathlib.Path(__file__).resolve().parents[2]
MINE = ROOT / "mining"
STATE_DIR = MINE / "crawl_state"
PROFILE = STATE_DIR / "profile"
POSTS = MINE / "posts"
STATE_FILE = STATE_DIR / "state.json"

for d in (MINE, STATE_DIR, POSTS):
    d.mkdir(parents=True, exist_ok=True)

SHORT_RE = re.compile(r"/(?:p|reel|tv)/([A-Za-z0-9_-]+)")
EXT_LINK_RE = re.compile(r"https?://(?:www\.)?(?!instagram\.com)[^\s\"'\)\]<>,]+")
ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")


def jload(p: pathlib.Path, default):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return default


def jdump(p: pathlib.Path, obj) -> None:
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(p)


def load_state() -> dict:
    st = jload(STATE_FILE, None)
    if not isinstance(st, dict):
        st = {}
    st.setdefault("username", "")
    st.setdefault("records", {})        # shortcode -> normalized record
    st.setdefault("queue", [])          # shortcodes awaiting fetch
    st.setdefault("fetched", {})        # shortcode -> True/failed
    st.setdefault("creators", {})       # username -> {id, scanned, next_max_id}
    st.setdefault("phase_saved_done", False)
    st.setdefault("stats", {})
    return st


def save_state(st: dict) -> None:
    jdump(STATE_FILE, st)


def nap(a: float = 2.0, b: float = 5.0) -> None:
    time.sleep(random.uniform(a, b))


def short_to_media_id(code: str) -> str:
    n = 0
    for ch in code:
        n = n * 64 + ALPHABET.index(ch)
    return str(n)


CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"


def launch():
    from playwright.sync_api import sync_playwright

    pw = sync_playwright().start()
    ctx = pw.chromium.launch_persistent_context(
        user_data_dir=str(PROFILE),
        headless=False,
        executable_path=CHROME_PATH,
        channel="chrome",
        locale="en-US",
        viewport={"width": 1280, "height": 920},
        args=[
            "--disable-blink-features=AutomationControlled",
            "--excludeSwitches=enable-automation",
            "--disable-infobars",
            "--no-first-run",
            "--no-default-browser-check",
            "--start-maximized",
        ],
        ignore_default_args=["--enable-automation"],
    )
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    # hide navigator.webdriver and other tells
    for p in ctx.pages:
        p.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
            "window.chrome = window.chrome || {runtime: {}};"
            "Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});"
            "Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});"
        )
    return pw, ctx


def is_logged_in(ctx) -> bool:
    names = {c["name"] for c in ctx.cookies()}
    return "ds_user_id" in names and "sessionid" in names


def wait_for_login(ctx, timeout_s: int) -> bool:
    end = time.time() + timeout_s
    while time.time() < end:
        if is_logged_in(ctx):
            time.sleep(3)
            return True
        time.sleep(5)
    return False


def detect_username(page):
    uid = next((c["value"] for c in page.context.cookies()
                if c["name"] == "ds_user_id"), None)
    if uid:
        try:
            r = api_fetch(page, f"/api/v1/users/{uid}/info/")
            u = (r.get("user") or {}).get("username")
            if u:
                return u
        except Exception:
            pass
    try:
        page.goto("https://www.instagram.com/saved/", wait_until="domcontentloaded")
        time.sleep(4)
        m = re.search(r"instagram\.com/([A-Za-z0-9._]+)/saved", page.url)
        if m:
            return m.group(1)
    except Exception:
        pass
    m = re.search(r'"username":"([A-Za-z0-9._]{1,30})"', page.content())
    return m.group(1) if m else None


def api_fetch(page, path: str):
    """GET an IG internal endpoint from inside the logged-in page."""
    r = page.evaluate(
        """async (path) => {
            const r = await fetch(path, {credentials: 'include',
                                          headers: {'x-ig-app-id': '936619743392459'}});
            return {status: r.status, body: await r.text()};
        }""", path)
    if r["status"] != 200:
        raise RuntimeError(f"HTTP {r['status']} for {path}")
    return json.loads(r["body"])
