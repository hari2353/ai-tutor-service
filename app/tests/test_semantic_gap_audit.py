import json
import io
import sys
from pathlib import Path
from urllib.error import URLError

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import semantic_gap_audit as sga  # noqa: E402


class FakeEmbedder:
    def __init__(self, vectors):
        self.vectors = vectors

    def embed(self, texts):
        return [self.vectors[text] for text in texts]


def _module(module_id, text):
    return sga.Module(
        id=module_id,
        title=module_id,
        track_title="Test track",
        source=Path(module_id + ".md"),
        text=text,
    )


def test_audit_ranks_semantic_matches_and_keeps_fixed_buckets():
    modules = [
        _module("T01-near", "near module"),
        _module("T02-close", "close module"),
        _module("T03-tie", "tie module"),
    ]
    embedder = FakeEmbedder({
        "near module": [1.0, 0.0],
        "close module": [0.8, 0.6],
        "tie module": [0.8, 0.6],
        "covered topic": [1.0, 0.0],
        "partial topic": [-0.1, 0.995],
        "missing topic": [0.0, -1.0],
    })

    report = sga.audit_topics(
        ["covered topic", "partial topic", "missing topic"], modules, embedder
    )

    assert [result.classification for result in report.results] == [
        "covered", "partial", "gap"
    ]
    assert report.results[0].matches[0].module.id == "T01-near"
    # Equal semantic scores are resolved by module id, not by provider order.
    assert [match.module.id for match in report.results[1].matches[:2]] == [
        "T02-close", "T03-tie"
    ]


def test_ollama_embedder_posts_batches_to_api_embed():
    requests = []

    class Response:
        def __init__(self, payload):
            self.payload = json.dumps(payload).encode("utf-8")

        def read(self, _limit=-1):
            return self.payload

        def close(self):
            pass

    def opener(request, timeout):
        requests.append((request, timeout))
        body = json.loads(request.data.decode("utf-8"))
        return Response({"embeddings": [[float(i)] for i in range(len(body["input"]))]})

    embedder = sga.OllamaEmbedder(
        base_url="http://127.0.0.1:11434", model="test-model", batch_size=2,
        opener=opener, timeout=7,
    )

    assert embedder.embed(["one", "two", "three"]) == [[0.0], [1.0], [0.0]]
    assert len(requests) == 2
    assert requests[0][0].full_url == "http://127.0.0.1:11434/api/embed"
    assert json.loads(requests[0][0].data.decode("utf-8")) == {
        "model": "test-model", "input": ["one", "two"]
    }
    assert requests[0][1] == 7


def test_ollama_unavailability_is_a_specific_failure():
    def opener(_request, timeout):
        raise URLError("connection refused")

    embedder = sga.OllamaEmbedder(opener=opener)
    with pytest.raises(sga.OllamaUnavailable, match="unavailable"):
        embedder.embed(["topic"])


def test_loader_resolves_module_id_with_trailing_metadata():
    modules = sga.load_modules()
    snowflake = next(module for module in modules if module.id == "T18-snowflake")

    assert snowflake.source.name == "05-snowflake.md"
    assert "Micro-partitions" in snowflake.text


def test_remote_endpoint_requires_explicit_opt_in():
    with pytest.raises(ValueError, match="localhost"):
        sga.OllamaEmbedder(base_url="https://example.test")

    embedder = sga.OllamaEmbedder(
        base_url="https://example.test", allow_remote=True, opener=lambda *_args, **_kwargs: None
    )
    assert embedder.endpoint == "https://example.test/api/embed"

    with pytest.raises(ValueError, match="query or fragment"):
        sga.OllamaEmbedder(base_url="http://127.0.0.1:11434?bad=true")


def test_loader_rejects_track_directory_outside_repository(tmp_path):
    outside = tmp_path.parent / "outside-curriculum"
    outside.mkdir()
    (outside / "module.md").write_text("outside", encoding="utf-8")
    data_dir = tmp_path / "app" / "data"
    data_dir.mkdir(parents=True)
    (data_dir / "curriculum.json").write_text(json.dumps({
        "tracks": [{
            "dir": "../outside-curriculum",
            "title": "Untrusted",
            "modules": [{"id": "T01-test", "title": "Test", "slug": "module", "tags": []}],
        }]
    }), encoding="utf-8")

    with pytest.raises(ValueError, match="escapes repository"):
        sga.load_modules(tmp_path)


def test_cosine_handles_large_finite_components_without_overflow():
    assert sga.cosine([1e308, 1e308], [1e308, 1e308]) == pytest.approx(1.0)


def test_report_uses_ascii_separator_for_legacy_windows_console(capsys):
    module = _module("T01-test", "test module")
    report = sga.AuditReport((sga.TopicResult(
        topic="test", classification="covered",
        matches=(sga.Match(1.0, module),),
    ),))

    sga._print_report(report, 1)

    assert "T01-test - T01-test" in capsys.readouterr().out


def test_report_replaces_unencodable_title_for_legacy_console(monkeypatch):
    output = io.StringIO()

    class LegacyConsole:
        encoding = "cp1252"

        def write(self, text):
            encoded = text.encode(self.encoding)
            output.write(encoded.decode(self.encoding))
            return len(text)

        def flush(self):
            pass

    monkeypatch.setattr(sga.sys, "stdout", LegacyConsole())
    module = _module("T01-test", "test module")
    module = sga.Module(module.id, "title √", module.track_title, module.source, module.text)

    sga._print_report(sga.AuditReport((sga.TopicResult(
        topic="test", classification="covered", matches=(sga.Match(1.0, module),),
    ),)), 1)

    assert "title ?" in output.getvalue()


def test_cli_returns_operational_error_when_ollama_is_unavailable(tmp_path, monkeypatch, capsys):
    topics = tmp_path / "topics.txt"
    topics.write_text("topic\n", encoding="utf-8")

    class UnavailableEmbedder:
        def __init__(self, *_args, **_kwargs):
            pass

        def embed(self, _texts):
            raise sga.OllamaUnavailable("unavailable")

    monkeypatch.setattr(sga, "OllamaEmbedder", UnavailableEmbedder)

    assert sga.main([str(topics)]) == 2
    assert "semantic gap audit unavailable" in capsys.readouterr().err


def test_input_validation_rejects_empty_topics_and_bad_vectors():
    with pytest.raises(ValueError, match="at least one topic"):
        sga.validate_topics([])

    class BadEmbedder:
        calls = 0

        def embed(self, _texts):
            self.calls += 1
            return [[1.0]] if self.calls == 1 else [[1.0, 2.0]]

    with pytest.raises(ValueError, match="same dimensionality"):
        sga.audit_topics(["one"], [_module("T01-one", "one")], BadEmbedder())
