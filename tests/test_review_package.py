from pathlib import Path
import subprocess
import sys

from gitutil import git, init_repo

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
REVIEW = SCRIPTS / "review-package"


def _commit(cwd: Path, name: str, content: str, message: str) -> str:
    path = cwd / name
    path.write_text(content)
    git(cwd, "add", name)
    git(cwd, "-c", "user.email=sdd@test", "-c", "user.name=sdd", "commit", "-m", message)
    return git(cwd, "rev-parse", "HEAD").strip()


def test_package_includes_all_commits_not_only_last(tmp_path: Path) -> None:
    init_repo(tmp_path)
    base = git(tmp_path, "rev-parse", "HEAD").strip()
    _commit(tmp_path, "a.txt", "one\n", "task commit 1")
    head = _commit(tmp_path, "b.txt", "two\n", "task commit 2")
    out = tmp_path / "pkg.diff.md"
    result = subprocess.run(
        [sys.executable, str(REVIEW), base, head, "-o", str(out)],
        cwd=tmp_path,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == str(out)
    text = out.read_text()
    assert "task commit 1" in text
    assert "task commit 2" in text
    assert "a.txt" in text
    assert "b.txt" in text
    one_parent = git(tmp_path, "rev-parse", "HEAD~1").strip()
    # The package must not be equivalent to HEAD~1..HEAD (which would drop commit 1).
    only_last = subprocess.check_output(
        ["git", "log", "--oneline", f"{one_parent}..{head}"],
        cwd=tmp_path,
        text=True,
    )
    assert "task commit 1" not in only_last
    assert "task commit 1" in text
    assert "## Diff" in text
    assert "+one" in text
    assert "+two" in text
    assert "diff --git" in text


def test_requires_dash_o(tmp_path: Path) -> None:
    init_repo(tmp_path)
    sha = git(tmp_path, "rev-parse", "HEAD").strip()
    result = subprocess.run(
        [sys.executable, str(REVIEW), sha, sha],
        cwd=tmp_path,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 2


def test_rejects_reversed_range(tmp_path: Path) -> None:
    init_repo(tmp_path)
    base = git(tmp_path, "rev-parse", "HEAD").strip()
    head = _commit(tmp_path, "a.txt", "one\n", "forward")
    out = tmp_path / "pkg.diff.md"
    result = subprocess.run(
        [sys.executable, str(REVIEW), head, base, "-o", str(out)],
        cwd=tmp_path,
        text=True,
        capture_output=True,
    )
    assert result.returncode != 0
    assert not out.exists()
    assert "Traceback" not in result.stderr


def test_rejects_unrelated_histories(tmp_path: Path) -> None:
    init_repo(tmp_path)
    first = git(tmp_path, "rev-parse", "HEAD").strip()
    git(tmp_path, "checkout", "--orphan", "other")
    git(tmp_path, "-c", "user.email=sdd@test", "-c", "user.name=sdd", "commit", "--allow-empty", "-m", "orphan")
    other = git(tmp_path, "rev-parse", "HEAD").strip()
    out = tmp_path / "pkg.diff.md"
    result = subprocess.run(
        [sys.executable, str(REVIEW), first, other, "-o", str(out)],
        cwd=tmp_path,
        text=True,
        capture_output=True,
    )
    assert result.returncode != 0
    assert not out.exists()


def test_non_utf8_diff_does_not_traceback(tmp_path: Path) -> None:
    init_repo(tmp_path)
    base = git(tmp_path, "rev-parse", "HEAD").strip()
    path = tmp_path / "latin1.txt"
    path.write_bytes(b"caf\xe9\n")
    git(tmp_path, "add", "latin1.txt")
    git(
        tmp_path,
        "-c",
        "user.email=sdd@test",
        "-c",
        "user.name=sdd",
        "-c",
        "core.hooksPath=/dev/null",
        "commit",
        "--no-verify",
        "-m",
        "latin1",
    )
    head = git(tmp_path, "rev-parse", "HEAD").strip()
    out = tmp_path / "pkg.diff.md"
    result = subprocess.run(
        [sys.executable, str(REVIEW), base, head, "-o", str(out)],
        cwd=tmp_path,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stderr
    assert "Traceback" not in result.stderr
    assert out.is_file()
    assert "latin1.txt" in out.read_text(encoding="utf-8")


def test_help_exits_zero() -> None:
    from sddlib.review import main as review_main

    result = subprocess.run(
        [sys.executable, str(REVIEW), "--help"],
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0
    assert "-o" in result.stdout or "--output" in result.stdout
    assert review_main(["--help"]) == 0
