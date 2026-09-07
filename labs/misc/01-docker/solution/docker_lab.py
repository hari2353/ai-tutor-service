"""Lab 01 — Docker without Docker. Reference solution."""
from __future__ import annotations

import hashlib
import json
import re
from typing import Dict, List, NamedTuple, Optional, Tuple, Union

KNOWN_INSTRUCTIONS = {
    "FROM", "RUN", "COPY", "ENV", "EXPOSE", "CMD", "ENTRYPOINT",
    "WORKDIR", "USER", "ARG",
}

_SECRET_KEYS = re.compile(r"SECRET|PASSWORD|TOKEN|_KEY$|KEY$", re.IGNORECASE)


# ------------------------------------------------------------------ 1. parser

def _logical_lines(text: str) -> List[str]:
    """Physical lines -> logical instruction lines (continuations joined, comments dropped)."""
    logical: List[str] = []
    buf: Optional[List[str]] = None  # segments of an in-progress continuation
    for raw in text.splitlines():
        line = raw.strip()
        if buf is not None:
            # inside a continuation: comments are dropped, code continues the instruction
            if line.startswith("#"):
                continue
            if line.endswith("\\"):
                buf.append(line[:-1].rstrip())
            else:
                buf.append(line)
                logical.append(" ".join(seg for seg in buf if seg))
                buf = None
            continue
        if not line or line.startswith("#"):
            continue
        if line.endswith("\\"):
            buf = [line[:-1].rstrip()]
        else:
            logical.append(line)
    if buf:  # file ended mid-continuation — flush what we have
        logical.append(" ".join(seg for seg in buf if seg))
    return logical


def _split_args(instruction: str, rest: str) -> Union[List[str], List[List[str]]]:
    """CMD/ENTRYPOINT exec form is a JSON list; everything else is whitespace-split."""
    stripped = rest.strip()
    if instruction in ("CMD", "ENTRYPOINT") and stripped.startswith("["):
        return json.loads(stripped)
    return stripped.split()


def parse_dockerfile(text: str) -> List[dict]:
    instructions: List[dict] = []
    for line in _logical_lines(text):
        keyword, _, rest = line.partition(" ")
        ins = keyword.upper()
        instructions.append({
            "instruction": ins,
            "args": _split_args(ins, rest),
            "raw": line,
        })
    return instructions


# ------------------------------------------------------------------ 2. layer cache

class Layer(NamedTuple):
    instruction: str
    args: Union[List[str], List[List[str]]]
    key: tuple
    digest: str
    cached: bool


class BuildResult(NamedTuple):
    image_layers: List[dict]
    cache_hits: int
    cache_misses: int


class LayerCache:
    def __init__(self) -> None:
        self.previous: List[tuple] = []

    @staticmethod
    def _copy_content_hash(args: List[str], files: Dict[str, str]) -> str:
        h = hashlib.sha256()
        for src in args[:-1]:  # last arg is the destination
            content = files.get(src, "")
            h.update(src.encode())
            h.update(b"\x00")
            h.update(content.encode())
            h.update(b"\x01")
        return h.hexdigest()

    def _layer_key(self, ins: dict, files: Dict[str, str]) -> tuple:
        if ins["instruction"] == "COPY":
            return ("COPY", tuple(ins["args"]), self._copy_content_hash(ins["args"], files))
        return (ins["instruction"], tuple(str(a) for a in ins["args"]))

    def build(self, instructions: List[dict], files: Optional[Dict[str, str]] = None
              ) -> BuildResult:
        files = files or {}
        image_layers: List[dict] = []
        hits = 0
        cascade_broken = False
        keys: List[tuple] = []
        for i, ins in enumerate(instructions):
            key = self._layer_key(ins, files)
            keys.append(key)
            cached = (
                i < len(self.previous)
                and not cascade_broken
                and self.previous[i] == key
            )
            if not cached:
                cascade_broken = True
            image_layers.append({
                "instruction": ins["instruction"],
                "args": ins["args"],
                "digest": hashlib.sha256(repr(key).encode()).hexdigest(),
                "cached": cached,
            })
            hits += cached
        self.previous = keys
        return BuildResult(image_layers, hits, len(instructions) - hits)


# ------------------------------------------------------------------ 3. linter

def _from_is_pinned(args: List[str]) -> bool:
    base = args[0]
    if "@" in base:  # digest-pinned — gold standard
        return True
    return ":" in base and base.split(":")[-1] != "latest"


def lint_dockerfile(instructions: List[dict]) -> List[dict]:
    findings: List[dict] = []
    instrs = [i["instruction"] for i in instructions]

    if "FROM" not in instrs:
        findings.append({"severity": "ERROR", "code": "E003",
                         "message": "no FROM — not a buildable image"})
        return findings

    # E002: non-ARG before the first FROM
    for i in instructions:
        if i["instruction"] == "FROM":
            break
        if i["instruction"] != "ARG":
            findings.append({"severity": "ERROR", "code": "E002",
                             "message": f"{i['instruction']} appears before the first FROM"})
            break

    # E001: two ENTRYPOINTs
    if instrs.count("ENTRYPOINT") > 1:
        findings.append({"severity": "ERROR", "code": "E001",
                         "message": "two ENTRYPOINTs — the second wins; the first is dead config"})

    # W004: multiple CMDs
    if instrs.count("CMD") > 1:
        findings.append({"severity": "WARN", "code": "W004",
                         "message": "multiple CMDs — only the last takes effect"})

    # W001: unpinned base (latest tag or no tag), once per offending FROM
    for i in instructions:
        if i["instruction"] == "FROM" and not _from_is_pinned(i["args"]):
            findings.append({"severity": "WARN", "code": "W001",
                             "message": f"unpinned base image tag: {i['args'][0]}"})

    # W002: no EXPOSE
    if "EXPOSE" not in instrs:
        findings.append({"severity": "WARN", "code": "W002",
                         "message": "no EXPOSE — implicit ports hurt discoverability"})

    # W003: no USER before the first RUN
    def _w003():
        for i in instructions:
            if i["instruction"] == "RUN":
                findings.append({"severity": "WARN", "code": "W003",
                                 "message": "runs as root: no USER before the first RUN"})
                return
            if i["instruction"] == "USER":
                return
    _w003()

    # W005: ENV keys that look like secrets, once per ENV
    for i in instructions:
        if i["instruction"] != "ENV" or not i["args"]:
            continue
        key = i["args"][0].split("=")[0]
        if _SECRET_KEYS.search(key):
            findings.append({"severity": "WARN", "code": "W005",
                             "message": f"ENV {key} looks like a secret — it ships in the image and docker history"})
            break

    return findings


# ------------------------------------------------------------------ 4. command knowledge

COMMANDS: Dict[str, str] = {
    "run": "create and start a new container from an image",
    "ps": "list containers (add -a to include stopped ones)",
    "exec": "run a command inside a running container",
    "logs": "fetch a container's stdout/stderr logs (add -f to follow)",
    "inspect": "show low-level JSON metadata of any Docker object",
    "images": "list local images and their sizes",
    "pull": "download an image from a registry to the local store",
    "build": "build an image from a Dockerfile and build context",
    "tag": "create an additional name (tag) pointing at an image",
    "push": "upload a local image to a registry",
    "cp": "copy files/folders between a container and the local filesystem",
    "stats": "live resource-usage stats (CPU/mem/net) for containers",
    "system prune": "remove unused data: stopped containers, dangling images, unused networks",
    "network create": "create a new container network",
    "volume ls": "list volumes — named mount points that outlive containers",
}

_COMMANDS_LOWER = {k: v for k, v in COMMANDS.items()}


def docker_command_help(cmd: str) -> str:
    name = cmd.strip()
    if name.lower().startswith("docker "):
        name = name[len("docker "):]
    return _COMMANDS_LOWER[name.lower()]


# ------------------------------------------------------------------ 5. exit codes

EXIT_CODES: Dict[int, str] = {
    0: "ok — application exited cleanly",
    1: "application error — the process itself failed",
    125: "docker daemon itself failed (e.g. unknown flag, unsupported option)",
    126: "command found but not executable (permission denied)",
    127: "command not found inside the container",
    137: "SIGKILL — killed (128+9), most commonly the OOM killer",
    143: "SIGTERM — clean termination request (128+15), the default stop signal",
}


def exit_code_decoder(code: int) -> str:
    return EXIT_CODES[code]
