#!/usr/bin/env python3
"""Rank curriculum matches with a local Ollama embedding model.

This is intentionally separate from ``gap_audit.py``. The lexical audit remains
useful offline; this command adds semantic retrieval without adding a Python
client dependency or a dependency on another repository.

Usage:
    python scripts/semantic_gap_audit.py topics.txt
    python scripts/semantic_gap_audit.py --stdin --top-k 3

Ollama configuration:
    OLLAMA_BASE_URL       default: http://127.0.0.1:11434
    OLLAMA_EMBED_MODEL    default: nomic-embed-text
"""
from __future__ import annotations

import argparse
import json
import math
import os
import pathlib
import re
import sys
from dataclasses import dataclass
from typing import Callable, Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener, urlopen

ROOT = pathlib.Path(__file__).resolve().parent.parent
DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434"
DEFAULT_EMBED_MODEL = "nomic-embed-text"
DEFAULT_TOP_K = 3
MAX_TOPIC_LENGTH = 1000
MAX_MODULE_TEXT = 24000
MAX_RESPONSE_BYTES = 32 * 1024 * 1024
EMBED_BATCH_SIZE = 32

# Fixed, model-independent boundaries make a run reproducible for the same
# embeddings. They deliberately produce triage buckets, not a truth judgment.
COVERED_THRESHOLD = 0.60
PARTIAL_THRESHOLD = 0.30


class OllamaUnavailable(RuntimeError):
    """The local embedding service could not complete an embedding request."""


class _RejectRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise OllamaUnavailable(f"Ollama returned an unexpected redirect to {newurl}")


_NO_REDIRECT_OPENER = build_opener(_RejectRedirects)


def _no_redirect_urlopen(request, timeout=30):
    return _NO_REDIRECT_OPENER.open(request, timeout=timeout)


@dataclass(frozen=True)
class Module:
    id: str
    title: str
    track_title: str
    source: pathlib.Path
    text: str


@dataclass(frozen=True)
class Match:
    score: float
    module: Module


@dataclass(frozen=True)
class TopicResult:
    topic: str
    classification: str
    matches: tuple[Match, ...]


@dataclass(frozen=True)
class AuditReport:
    results: tuple[TopicResult, ...]


def validate_topics(topics: Iterable[str]) -> list[str]:
    """Normalize and validate user-provided topics before making network calls."""
    cleaned = []
    for raw in topics:
        if not isinstance(raw, str):
            raise ValueError("topics must be strings")
        topic = raw.strip()
        if not topic or topic.startswith("#"):
            continue
        if len(topic) > MAX_TOPIC_LENGTH:
            raise ValueError(f"topic exceeds {MAX_TOPIC_LENGTH} characters")
        cleaned.append(topic)
    if not cleaned:
        raise ValueError("at least one topic is required")
    return cleaned


def _module_file(root: pathlib.Path, track_dir: str, module_id: str, slug: str) -> pathlib.Path | None:
    root = root.resolve()
    directory = (root / track_dir).resolve()
    try:
        directory.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"curriculum track directory escapes repository: {track_dir}") from exc
    if not directory.is_dir():
        return None
    candidates = sorted(directory.glob("*.md"))
    # Authored metadata may append tags or other fields after the id.
    id_pattern = re.compile(
        rf"^>?\s*\*\*Module id:\*\*\s*`{re.escape(module_id)}`(?:\s+.*)?$", re.M
    )
    for path in candidates:
        try:
            path.resolve().relative_to(root)
        except ValueError:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if id_pattern.search(text):
            return path
    by_slug = [path for path in candidates if path.stem.endswith(slug)]
    return by_slug[0] if len(by_slug) == 1 else None


def _searchable_text(module: dict, track: dict, body: str) -> str:
    # Include metadata plus the complete teaching text, bounded so a malformed
    # or unexpectedly large document cannot create an unbounded local request.
    metadata = " ".join([
        module.get("id", ""), module.get("title", ""), module.get("slug", ""),
        " ".join(module.get("tags", [])), track.get("title", ""),
    ])
    return f"{metadata}\n{body[:MAX_MODULE_TEXT]}".strip()


def load_modules(root: pathlib.Path = ROOT) -> list[Module]:
    """Load every generated curriculum module and its authored markdown text."""
    path = root / "app" / "data" / "curriculum.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read curriculum data: {exc}") from exc

    modules = []
    for track in data.get("tracks", []):
        for module in track.get("modules", []):
            source = _module_file(root, track["dir"], module["id"], module["slug"])
            body = ""
            if source is not None:
                try:
                    body = source.read_text(encoding="utf-8", errors="ignore")
                except OSError:
                    body = ""
            modules.append(Module(
                id=module["id"], title=module["title"],
                track_title=track["title"], source=source or pathlib.Path(),
                text=_searchable_text(module, track, body),
            ))
    if not modules:
        raise ValueError("curriculum contains no modules")
    return sorted(modules, key=lambda module: module.id)


def _read_response(response) -> bytes:
    data = response.read(MAX_RESPONSE_BYTES + 1)
    if len(data) > MAX_RESPONSE_BYTES:
        raise ValueError("Ollama response exceeds the size limit")
    return data


class OllamaEmbedder:
    """Small injectable HTTP boundary for Ollama's ``/api/embed`` endpoint."""

    def __init__(
        self,
        base_url: str = DEFAULT_OLLAMA_URL,
        model: str = DEFAULT_EMBED_MODEL,
        batch_size: int = EMBED_BATCH_SIZE,
        opener: Callable = urlopen,
        timeout: float = 30,
        allow_remote: bool = False,
    ):
        base_url = base_url.strip()
        parsed_url = urlsplit(base_url)
        if parsed_url.scheme not in {"http", "https"}:
            raise ValueError("OLLAMA_BASE_URL must use http:// or https://")
        if not parsed_url.hostname or parsed_url.username or parsed_url.password:
            raise ValueError("OLLAMA_BASE_URL must contain a host without credentials")
        if parsed_url.query or parsed_url.fragment:
            raise ValueError("OLLAMA_BASE_URL must not contain a query or fragment")
        host = parsed_url.hostname
        local_hosts = {"localhost", "127.0.0.1", "::1"}
        if not host or (host not in local_hosts and not allow_remote):
            raise ValueError(
                "OLLAMA_BASE_URL must target localhost; pass --allow-remote for an explicit remote target"
            )
        if not model.strip() or len(model) > 200:
            raise ValueError("OLLAMA_EMBED_MODEL must be a non-empty short name")
        if not 1 <= batch_size <= 256:
            raise ValueError("batch_size must be between 1 and 256")
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        endpoint_path = parsed_url.path.rstrip("/") + "/api/embed"
        self.endpoint = urlunsplit((
            parsed_url.scheme, parsed_url.netloc, endpoint_path, "", ""
        ))
        self.model = model.strip()
        self.batch_size = batch_size
        self.opener = opener if opener is not urlopen else _no_redirect_urlopen
        self.timeout = timeout

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts or any(not isinstance(text, str) or not text.strip() for text in texts):
            raise ValueError("embedder input must contain non-empty strings")
        vectors = []
        for start in range(0, len(texts), self.batch_size):
            batch = texts[start:start + self.batch_size]
            payload = json.dumps({"model": self.model, "input": batch}).encode("utf-8")
            request = Request(
                self.endpoint, data=payload,
                headers={"Content-Type": "application/json"}, method="POST",
            )
            try:
                response = self.opener(request, timeout=self.timeout)
                try:
                    raw = _read_response(response)
                finally:
                    response.close()
            except (HTTPError, URLError, TimeoutError, OSError) as exc:
                raise OllamaUnavailable(f"Ollama unavailable at {self.endpoint}: {exc}") from exc
            try:
                result = json.loads(raw.decode("utf-8"))
                batch_vectors = result["embeddings"]
            except (UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError) as exc:
                raise ValueError("Ollama returned an invalid embedding response") from exc
            if not isinstance(batch_vectors, list) or len(batch_vectors) != len(batch):
                raise ValueError("Ollama returned the wrong number of embeddings")
            vectors.extend(batch_vectors)
        return [_validate_vector(vector) for vector in vectors]


def _validate_vector(vector) -> list[float]:
    if not isinstance(vector, list) or not vector:
        raise ValueError("embedding vectors must be non-empty arrays")
    try:
        values = [float(value) for value in vector]
    except (TypeError, ValueError) as exc:
        raise ValueError("embedding vectors must contain numbers") from exc
    if any(not math.isfinite(value) for value in values):
        raise ValueError("embedding vectors must contain finite numbers")
    return values


def cosine(left: list[float], right: list[float]) -> float:
    if len(left) != len(right):
        raise ValueError("embedding vectors must have the same dimensionality")
    # Normalize before multiplying so large, valid components cannot overflow.
    left_norm = math.hypot(*left)
    right_norm = math.hypot(*right)
    if left_norm == 0 or right_norm == 0:
        raise ValueError("embedding vectors must not be zero vectors")
    score = math.fsum(
        (a / left_norm) * (b / right_norm) for a, b in zip(left, right)
    )
    if not math.isfinite(score):
        raise ValueError("cosine similarity must be finite")
    return score


def _classification(score: float) -> str:
    if score >= COVERED_THRESHOLD:
        return "covered"
    if score >= PARTIAL_THRESHOLD:
        return "partial"
    return "gap"


def audit_topics(
    topics: list[str], modules: list[Module], embedder, top_k: int = DEFAULT_TOP_K
) -> AuditReport:
    topics = validate_topics(topics)
    if not modules:
        raise ValueError("at least one curriculum module is required")
    if not 1 <= top_k <= 20:
        raise ValueError("top_k must be between 1 and 20")
    module_vectors = embedder.embed([module.text for module in modules])
    topic_vectors = embedder.embed(topics)
    if len(module_vectors) != len(modules) or len(topic_vectors) != len(topics):
        raise ValueError("embedder returned the wrong number of vectors")
    module_vectors = [_validate_vector(vector) for vector in module_vectors]
    topic_vectors = [_validate_vector(vector) for vector in topic_vectors]

    results = []
    for topic, topic_vector in zip(topics, topic_vectors):
        matches = sorted(
            (Match(cosine(topic_vector, module_vector), module)
             for module, module_vector in zip(modules, module_vectors)),
            key=lambda match: (-match.score, match.module.id),
        )
        results.append(TopicResult(
            topic=topic, classification=_classification(matches[0].score),
            matches=tuple(matches[:top_k]),
        ))
    return AuditReport(tuple(results))


def _read_topics(args: argparse.Namespace) -> list[str]:
    if args.stdin:
        return validate_topics(sys.stdin.read().splitlines())
    if args.topic_file:
        try:
            return validate_topics(pathlib.Path(args.topic_file).read_text(encoding="utf-8").splitlines())
        except OSError as exc:
            raise ValueError(f"cannot read topic file: {exc}") from exc
    raise ValueError("provide a topic file or --stdin")


def _print_report(report: AuditReport, top_k: int) -> None:
    def write(line: str = "") -> None:
        try:
            print(line)
        except UnicodeEncodeError:
            encoding = sys.stdout.encoding or "ascii"
            print(line.encode(encoding, errors="replace").decode(encoding))

    counts = {name: sum(r.classification == name for r in report.results)
              for name in ("covered", "partial", "gap")}
    write(f"{len(report.results)} topics - {counts['covered']} covered - "
          f"{counts['partial']} partial - {counts['gap']} GAPS\n")
    for result in report.results:
        write(f"[{result.classification.upper()}] {result.topic}")
        for match in result.matches[:top_k]:
            write(f"  {match.score:.1%} {match.module.id} - {match.module.title}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group()
    source.add_argument("topic_file", nargs="?", help="one topic per line")
    source.add_argument("--stdin", action="store_true", help="read one topic per line from stdin")
    parser.add_argument("--top-k", type=int, default=DEFAULT_TOP_K)
    parser.add_argument("--ollama-url", default=os.environ.get("OLLAMA_BASE_URL", DEFAULT_OLLAMA_URL))
    parser.add_argument("--model", default=os.environ.get("OLLAMA_EMBED_MODEL", DEFAULT_EMBED_MODEL))
    parser.add_argument(
        "--allow-remote", action="store_true",
        help="allow sending curriculum text to a non-local Ollama endpoint",
    )
    args = parser.parse_args(argv)
    if not 1 <= args.top_k <= 20:
        parser.error("--top-k must be between 1 and 20")
    try:
        topics = _read_topics(args)
        modules = load_modules()
        report = audit_topics(
            topics, modules,
            OllamaEmbedder(args.ollama_url, args.model, allow_remote=args.allow_remote),
            args.top_k,
        )
    except OllamaUnavailable as exc:
        print(f"semantic gap audit unavailable: {exc}", file=sys.stderr)
        return 2
    except (ValueError, OSError) as exc:
        print(f"semantic gap audit input error: {exc}", file=sys.stderr)
        return 2
    _print_report(report, args.top_k)
    return 1 if any(result.classification == "gap" for result in report.results) else 0


if __name__ == "__main__":
    sys.exit(main())
