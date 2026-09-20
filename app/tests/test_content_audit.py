import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_content_audit_passes_against_built_repository():
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "content_audit.py")],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "content audit: OK" in result.stdout
