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
    # Non-main initial branch so callers can `checkout -b main`.
    git(cwd, "init", "-b", "sdd-base")
    git(cwd, "-c", "user.email=sdd@test", "-c", "user.name=sdd", "commit", "--allow-empty", "-m", "base")
