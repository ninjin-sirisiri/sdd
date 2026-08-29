from __future__ import annotations

from pathlib import Path
import argparse
import subprocess
import sys

from sddlib.cli import system_exit_code


def _git_text(cwd: Path, *args: str) -> str:
    raw = subprocess.check_output(["git", *args], cwd=cwd)
    return raw.decode("utf-8", errors="replace")


def write_review_package(base: str, head: str, out: Path, *, cwd: Path) -> Path:
    _git_text(cwd, "rev-parse", "--verify", f"{base}^{{commit}}")
    _git_text(cwd, "rev-parse", "--verify", f"{head}^{{commit}}")
    ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", base, head],
        cwd=cwd,
        capture_output=True,
    )
    if ancestor.returncode != 0:
        raise ValueError("BASE is not an ancestor of HEAD")
    log = _git_text(cwd, "log", "--oneline", f"{base}..{head}")
    stat = _git_text(cwd, "diff", "--stat", f"{base}..{head}")
    diff = _git_text(cwd, "diff", "-U10", f"{base}..{head}")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        f"# Review package: {base}..{head}\n\n"
        f"## Commits\n{log}\n"
        f"## Files changed\n{stat}\n"
        f"## Diff\n{diff}",
        encoding="utf-8",
    )
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="review-package")
    parser.add_argument("base")
    parser.add_argument("head")
    parser.add_argument("-o", "--output", required=True)
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return system_exit_code(exc)
    try:
        path = write_review_package(args.base, args.head, Path(args.output), cwd=Path.cwd())
    except subprocess.CalledProcessError:
        print("bad BASE or HEAD", file=sys.stderr)
        return 2
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"review-package failed: {exc}", file=sys.stderr)
        return 2
    print(path)
    return 0
