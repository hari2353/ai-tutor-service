"""macOS OCR for downloaded post images, mirroring run_ocr.py (which uses
Windows OCR). Uses the built-in Vision framework via pyobjc - no extra
binary. Writes/appends mining/posts/<code>/ocr.txt with slide text.

Run:  python scripts/ig_crawler/run_ocr_mac.py            # backfill all posts
"""
from __future__ import annotations

import io
import pathlib
import sys

sys.path.insert(0, pathlib.Path(__file__).resolve().parent)

import common

MIN_TEXT = 12  # chars; below this treat as empty (blank frame)


def _accessor(obj, name):
    """pyobjc exposes some members as properties, some as selector methods."""
    v = getattr(obj, name, None)
    return v() if callable(v) else v


def ocr_file(path: pathlib.Path) -> str:
    import Vision
    from Foundation import NSURL

    r = Vision.VNRecognizeTextRequest.alloc().init()
    r.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)

    # Vision reads HEIC natively via URL but not WebP; route WebP through
    # PIL -> PNG bytes.
    src: object
    if path.suffix.lower() in (".jpg", ".jpeg", ".png", ".heic", ".heif"):
        src = NSURL.fileURLWithPath_(str(path))
        handler = Vision.VNImageRequestHandler.alloc().initWithURL_options_(src, None)
    else:
        from PIL import Image
        img = Image.open(path)
        if img.mode != "RGB":
            img = img.convert("RGB")
        buf = io.BytesIO()
        img.save(buf, "PNG")
        handler = Vision.VNImageRequestHandler.alloc().initWithData_options_(
            buf.getvalue(), None)
    ok, _err = handler.performRequests_error_([r], None)
    if not ok:
        return ""
    res = _accessor(r, "results") or []
    # Vision returns lines in reading order already; no re-sort needed
    lines = []
    for obs in res:
        cand = obs.topCandidates_(1) or []
        if cand:
            line = _accessor(cand[0], "string")
            if line:
                lines.append(line)
    return "\n".join(lines).strip()


def ocr_post_dir(d: pathlib.Path) -> str:
    files = sorted(
        [f for f in d.glob("i*.jpg") if not f.name.endswith(".part")]
        + list(d.glob("v*_frame_*.jpg")),
        key=lambda f: (f.name[0], int("".join(ch for ch in f.name if ch.isdigit()) or 0)),
    )
    parts = []
    for f in files:
        text = ocr_file(f)
        if text and len(text) >= MIN_TEXT:
            parts.append(f"----- {f.name} -----\n{text}")
    return "\n\n".join(parts)


def main() -> None:
    todo = []
    for d in common.POSTS.iterdir():
        if not d.is_dir():
            continue
        p = d / "ocr.txt"
        if p.exists() and p.stat().st_size > 0:
            continue
        if any(d.glob("i*.jpg")) or any(d.glob("v*_frame_*.jpg")):
            todo.append(d)
    if not todo:
        print("DONE: nothing to OCR")
        return
    for d in todo:
        text = ocr_post_dir(d)
        if text:
            (d / "ocr.txt").write_text(text, encoding="utf-8")
            print(f"{d.name}: {len(text)} chars")
    print("DONE")


if __name__ == "__main__":
    main()
