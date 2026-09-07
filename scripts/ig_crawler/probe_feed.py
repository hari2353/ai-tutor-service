"""Probe: does /api/v1/feed/user/{id}/ work in this session? Try one known
educational creator (@thedataguy16). Falls back to checking the profile page
approach if not.
"""
from __future__ import annotations

import sys
import time

sys.path.insert(0, __file__.rsplit("\\", 1)[0])
import common

TARGET = 'thedataguy16'
Q = 'document.querySelectorAll(\'a[href*="/p/"]\').length'


def main():
    pw, ctx = common.launch()
    try:
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto('https://www.instagram.com/', wait_until='domcontentloaded')
        time.sleep(3)
        st = common.load_state()
        uid = (st['creators'].get(TARGET) or {}).get('id') or ''
        if not uid:
            u = common.api_fetch(page, f'/api/v1/users/web_profile_info/?username={TARGET}')
            uid = (u.get('data') or {}).get('user', {}).get('id')
            print('resolved id:', uid)
        try:
            data = common.api_fetch(page, f'/api/v1/feed/user/{uid}/?count=12')
            items = data.get('items') or []
            print(f'FEED OK: {len(items)} items, more={data.get("more_available")}')
            if items:
                it = items[0]
                print('first item code:', it.get('code'), '| media_type:', it.get('media_type'))
        except Exception as e:
            print('feed api failed:', str(e)[:120])
            page.goto(f'https://www.instagram.com/{TARGET}/', wait_until='domcontentloaded')
            time.sleep(5)
            n = page.evaluate(Q)
            print(f'profile page anchors visible: {n}')
    finally:
        try:
            ctx.close()
        except Exception:
            pass
        pw.stop()


if __name__ == '__main__':
    main()
