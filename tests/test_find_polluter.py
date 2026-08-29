from pathlib import Path
import subprocess

SCRIPT = Path(__file__).resolve().parents[1] / "skills" / "systematic-debugging" / "find-polluter.sh"


def test_existing_target_is_unmeasurable(tmp_path: Path) -> None:
    already = tmp_path / "already-there"
    already.write_text("x", encoding="utf-8")
    result = subprocess.run(
        ["bash", str(SCRIPT), str(already), "no-such-tests/*.py"],
        cwd=tmp_path,
        text=True,
        capture_output=True,
    )
    assert result.returncode != 0
    assert "No polluter found" not in result.stdout
    combined = result.stdout + result.stderr
    assert "already-there" in combined or "Cannot measure" in combined or "already exists" in combined
