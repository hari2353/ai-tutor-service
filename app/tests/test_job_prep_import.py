import json
from pathlib import Path

import pytest

from scripts.import_job_prep import import_manifest


def _manifest():
    return {
        "schema_version": 1,
        "jobs": [
            {
                "job_id": "linkedin_1",
                "company": "Pull Logic",
                "title": "Principal AI Engineer",
                "score": 92,
                "market": "India",
                "jd_snippet": "Build RAG systems.",
                "prep_pack_path": "interview_prep/prep_packs/pull_logic.md",
                "curriculum_matches": [],
                "curriculum_gaps": [],
            }
        ],
    }


def test_import_manifest_is_idempotent_and_does_not_overwrite(tmp_path):
    generated = tmp_path / "generated.md"
    generated.write_text("## Generated question\nAnswer", encoding="utf-8")
    manifest = _manifest()
    manifest["jobs"][0]["prep_pack_path"] = str(generated)
    source = tmp_path / "manifest.json"
    source.write_text(json.dumps(manifest), encoding="utf-8")
    inbox = tmp_path / "inbox"

    first = import_manifest(source, inbox)
    second = import_manifest(source, inbox)

    assert first == second == 1
    pack = inbox / "linkedin_1.md"
    metadata = inbox / "linkedin_1.json"
    assert pack.exists()
    assert metadata.exists()
    content = pack.read_text(encoding="utf-8")
    assert "Build RAG systems." in content
    assert "## Generated question" in content

    pack.write_text("canonical notes", encoding="utf-8")
    import_manifest(source, inbox)
    assert pack.read_text(encoding="utf-8") == "canonical notes"


def test_import_manifest_rejects_invalid_schema(tmp_path):
    source = tmp_path / "manifest.json"
    source.write_text(json.dumps({"schema_version": 2, "jobs": []}), encoding="utf-8")

    with pytest.raises(ValueError, match="schema_version"):
        import_manifest(source, tmp_path / "inbox")
