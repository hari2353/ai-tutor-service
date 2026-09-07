"""Normalization: raw IG API/GraphQL payloads -> one record shape.

Handles both the private mobile API shape (api/v1/feed/...) and the GraphQL
web shape (xdt_api__graphql... or legacy), wherever the post data happens to
live in the response tree.
"""
from __future__ import annotations

import re


def _walk_for_media_items(node, acc=None, depth=0):
    """Find nodes that look like a post with media, anywhere in the tree."""
    acc = acc if acc is not None else []
    if depth > 12:
        return acc
    if isinstance(node, dict):
        if _looks_like_post(node):
            acc.append(node)
        for v in node.values():
            _walk_for_media_items(v, acc, depth + 1)
    elif isinstance(node, list):
        for v in node:
            _walk_for_media_items(v, acc, depth + 1)
    return acc


def _looks_like_post(n: dict) -> bool:
    if not isinstance(n, dict):
        return False
    code = n.get("code") or n.get("shortcode")
    if not code:
        return False
    has_media = ("image_versions2" in n or "carousel_media" in n
                 or "video_versions" in n or "display_url" in n
                 or "display_resources" in n)
    has_owner = "user" in n or "owner" in n
    return has_media or has_owner


def _caption_of(n: dict):
    cap = n.get("caption")
    if isinstance(cap, dict):
        return cap.get("text") or ""
    if isinstance(cap, str):
        return cap
    try:
        return n["edge_media_to_caption"]["edges"][0]["node"]["text"]
    except Exception:
        return ""


def _user_of(n: dict):
    u = n.get("user") or n.get("owner") or {}
    if isinstance(u, dict):
        return u
    return {}


def _media_items(n: dict):
    items = []
    children = n.get("carousel_media")
    sources = children if children else [n]
    for m in sources:
        if not isinstance(m, dict):
            continue
        vv = m.get("video_versions") or []
        if vv:
            items.append({"kind": "video", "url": vv[0].get("url") or ""})
            continue
        cands = (m.get("image_versions2") or {}).get("candidates") or []
        if cands:
            best = max(cands, key=lambda c: c.get("width") or 0)
            items.append({"kind": "image", "url": best.get("url") or ""})
            continue
        if m.get("is_video") and m.get("video_url"):
            items.append({"kind": "video", "url": m["video_url"]})
            continue
        dr = m.get("display_resources") or []
        src = (dr[-1]["src"] if dr else m.get("display_url")) or ""
        if src:
            items.append({"kind": "image", "url": src})
    return items


def normalize_post(node: dict, source: str) -> dict:
    user = _user_of(node)
    code = node.get("code") or node.get("shortcode") or ""
    return {
        "shortcode": code,
        "source": source,
        "creator_username": user.get("username") or "",
        "creator_full_name": user.get("full_name") or "",
        "creator_id": str(user.get("pk") or user.get("id") or ""),
        "creator_verified": bool(user.get("is_verified")),
        "caption": _caption_of(node),
        "taken_at": node.get("taken_at"),
        "like_count": node.get("like_count"),
        "comment_count": node.get("comment_count"),
        "media_type": node.get("media_type"),
        "items": _media_items(node),
    }


def extract_posts(payload: dict, source: str) -> list[dict]:
    """Walk any response payload, pull out normalized post records."""
    found = _walk_for_media_items(payload)
    seen, out = set(), []
    for n in found:
        rec = normalize_post(n, source)
        code = rec["shortcode"]
        if code and code not in seen and rec["items"]:
            seen.add(code)
            out.append(rec)
    return out


def extract_permalinks(payload) -> list[str]:
    text = payload if isinstance(payload, str) else __import__("json").dumps(payload)
    return [m.group(1) for m in re.finditer(r"/p/([A-Za-z0-9_-]+)", text)]
