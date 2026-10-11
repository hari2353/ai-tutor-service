"""Import job-hunt prep evidence without mutating the curriculum."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")


def _read_manifest(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"could not read manifest: {exc}") from exc
    if data.get("schema_version") != 1:
        raise ValueError("unsupported schema_version")
    if not isinstance(data.get("jobs"), list):
        raise ValueError("manifest jobs must be a list")
    return data


def _source_markdown(job: dict) -> str:
    company = job.get("company") or "Unknown"
    title = job.get("title") or "Unknown"
    jd = job.get("jd_snippet") or "(no JD snippet provided)"
    matches = job.get("curriculum_matches") or []
    pack_path = Path(str(job.get("prep_pack_path") or ""))
    generated_pack = ""
    if pack_path.is_file():
        try:
            generated_pack = pack_path.read_text(encoding="utf-8", errors="ignore")[:20000]
        except OSError:
            generated_pack = ""
    lines = [
        f"# Job Prep Intake — {company} ({title})",
        "",
        f"- job_id: `{job['job_id']}`",
        f"- source: `job-hunt-ai`",
        f"- score: {job.get('score', 'unknown')}",
        f"- market: {job.get('market') or 'unknown'}",
        "",
        "## Job Description Evidence",
        "",
        jd,
        "",
    ]
    if generated_pack:
        lines += ["## Generated Interview Prep Pack", "", generated_pack, ""]
    lines += ["## Tutor Curriculum Matches", ""]
    if matches:
        lines.extend(
            f"- `{m.get('module_id', '')}` {m.get('title', '')} "
            f"({m.get('verdict', 'unknown')}, {m.get('score', 0):.0%})"
            for m in matches
        )
    else:
        lines.append("_No curriculum match was available at export time._")
    return "\n".join(lines) + "\n"


def import_manifest(manifest_path: Path | str, inbox: Path | str) -> int:
    manifest = _read_manifest(Path(manifest_path))
    inbox = Path(inbox)
    inbox.mkdir(parents=True, exist_ok=True)
    imported = 0
    for job in manifest["jobs"]:
        if not isinstance(job, dict):
            continue
        job_id = str(job.get("job_id") or "")
        if not SAFE_ID.fullmatch(job_id):
            continue
        md_path = inbox / f"{job_id}.md"
        metadata_path = inbox / f"{job_id}.json"
        if not md_path.exists():
            md_path.write_text(_source_markdown(job), encoding="utf-8")
        if not metadata_path.exists():
            metadata_path.write_text(
                json.dumps({
                    "schema_version": 1,
                    "job_id": job_id,
                    "company": job.get("company", ""),
                    "title": job.get("title", ""),
                    "source": "job-hunt-ai",
                    "prep_pack_path": job.get("prep_pack_path", ""),
                    "curriculum_matches": job.get("curriculum_matches", []),
                }, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
        imported += 1
    return imported


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--inbox", type=Path,
                        default=Path(__file__).resolve().parents[1] / "mocks" / "company" / "inbox")
    args = parser.parse_args()
    print(f"Imported {import_manifest(args.manifest, args.inbox)} job prep record(s)")


if __name__ == "__main__":
    main()
