from pathlib import Path
import subprocess
import sys

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
BRIEF = SCRIPTS / "task-brief"
FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _run(cwd: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(BRIEF), *args],
        cwd=cwd,
        text=True,
        capture_output=True,
    )


def test_extracts_only_task_two(tmp_path: Path) -> None:
    plan = tmp_path / "plan.md"
    plan.write_text((FIXTURES / "plan" / "2026-01-01-example.md").read_text())
    result = _run(tmp_path, [str(plan), "2"])
    assert result.returncode == 0, result.stderr
    out = Path(result.stdout.strip())
    assert out == tmp_path / ".sdd" / "briefs" / "task-2-brief.md"
    text = out.read_text()
    assert text.startswith("## Task 2: Second thing")
    assert "UNIQUE_TASK_TWO" in text
    assert "UNIQUE_TASK_ONE" not in text
    assert "**Goal:**" not in text


def test_skips_headings_inside_fences(tmp_path: Path) -> None:
    plan = tmp_path / "plan.md"
    plan.write_text(
        "# Plan\n\n"
        "## Task 1: Real one\n\n"
        "alpha\n\n"
        "```markdown\n"
        "## Task 2: Fake inside fence\n"
        "```\n\n"
        "still task one\n\n"
        "## Task 2: Real two\n\n"
        "beta\n"
    )
    result = _run(tmp_path, [str(plan), "1"])
    assert result.returncode == 0, result.stderr
    text = Path(result.stdout.strip()).read_text()
    assert "still task one" in text
    assert "Fake inside fence" in text  # fenced content is still inside Task 1
    assert "## Task 2: Real two" not in text
    result2 = _run(tmp_path, [str(plan), "2"])
    assert result2.returncode == 0
    text2 = Path(result2.stdout.strip()).read_text()
    assert text2.startswith("## Task 2: Real two")
    assert "beta" in text2
    assert "still task one" not in text2


def test_missing_task_is_exit_3(tmp_path: Path) -> None:
    plan = tmp_path / "plan.md"
    plan.write_text((FIXTURES / "plan" / "2026-01-01-example.md").read_text())
    result = _run(tmp_path, [str(plan), "9"])
    assert result.returncode == 3
    assert not (tmp_path / ".sdd" / "briefs" / "task-9-brief.md").exists()
