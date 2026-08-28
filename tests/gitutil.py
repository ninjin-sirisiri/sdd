from pathlib import Path
import subprocess


def git(cwd: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        text=True,
        capture_output=True,
    )
    return result.stdout


def init_repo(cwd: Path) -> None:
    git(cwd, "init")
    git(cwd, "-c", "user.email=sdd@test", "-c", "user.name=sdd", "commit", "--allow-empty", "-m", "base")
