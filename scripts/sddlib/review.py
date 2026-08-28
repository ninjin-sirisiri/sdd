from __future__ import annotations

from pathlib import Path
import argparse
import subprocess
import sys


def write_review_package(base: str, head: str, out: Path, *, cwd: Path) -> Path:
    subprocess.check_output(["git", "rev-parse", "--verify", base], cwd=cwd)
    subprocess.check_output(["git", "rev-parse", "--verify", head], cwd=cwd)
    log = subprocess.check_output(["git", "log", "--oneline", f"{base}..{head}"], cwd=cwd, text=True)
    stat = subprocess.check_output(["git", "diff", "--stat", f"{base}..{head}"], cwd=cwd, text=True)
    diff = subprocess.check_output(["git", "diff", "-U10", f"{base}..{head}"], cwd=cwd, text=True)
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
        return int(exc.code or 2)
    try:
        path = write_review_package(args.base, args.head, Path(args.output), cwd=Path.cwd())
    except subprocess.CalledProcessError:
        print("bad BASE or HEAD", file=sys.stderr)
        return 2
    print(path)
    return 0
