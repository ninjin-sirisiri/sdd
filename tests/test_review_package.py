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
