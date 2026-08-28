from __future__ import annotations

from pathlib import Path
import argparse
import subprocess
import sys

from sddlib.ledger import extract_goal, extract_task_heading, parse_ledger


def _git(cwd: Path, *args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=cwd, text=True)


def run_stack(
    *,
    cwd: Path,
    base_branch: str,
    ledger_path: Path,
    plan_path: Path,
    dry_run: bool,
    update_ref=None,
    push=None,
    gh=None,
) -> int:
    if not ledger_path.is_file():
        print("missing ledger", file=sys.stderr)
        return 1
    items = parse_ledger(ledger_path.read_text(encoding="utf-8"))
    if not items:
        print("no complete tasks in ledger", file=sys.stderr)
        return 1
    plan_text = plan_path.read_text(encoding="utf-8")
    goal = extract_goal(plan_text)
    created: list[str] = []
    for index, item in enumerate(items):
        branch = f"sdd-stack/task-{item.number}"
        pr_base = base_branch if index == 0 else f"sdd-stack/task-{items[index - 1].number}"
        heading = extract_task_heading(plan_text, item.number) or branch
        if dry_run:
            print(f"{branch} base={pr_base}")
            continue
        try:
            sha = _git(cwd, "rev-parse", "--verify", item.head).strip()
            (update_ref or (_default_update_ref(cwd)))(branch, sha)
            (push or (_default_push(cwd)))(branch)
            url = (gh or (_default_gh(cwd)))(
                [
                    "pr",
                    "create",
                    "--base",
                    pr_base,
                    "--head",
                    branch,
                    "--title",
                    heading,
                    "--body",
                    f"{goal}\n\n{heading}",
                ]
            )
            created.append(url.strip())
            print(url.strip())
        except Exception as exc:  # noqa: BLE001
            remaining = [t.number for t in items[index:]]
            print(f"failed at task {item.number}: {exc}", file=sys.stderr)
            print("created: " + ", ".join(created), file=sys.stderr)
            print("remaining: " + ", ".join(str(n) for n in remaining), file=sys.stderr)
            return 1
    return 0


def _default_update_ref(cwd: Path):
    def _run(branch: str, sha: str) -> None:
        _git(cwd, "update-ref", f"refs/heads/{branch}", sha)

    return _run


def _default_push(cwd: Path):
    def _run(branch: str) -> None:
        subprocess.check_call(["git", "push", "origin", branch], cwd=cwd)

    return _run


def _default_gh(cwd: Path):
    def _run(args: list[str]) -> str:
        return subprocess.check_output(["gh", *args], cwd=cwd, text=True)

    return _run


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="stack-prs")
    parser.add_argument("--base", required=True)
    parser.add_argument("--ledger", required=True, type=Path)
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--dry-run", action="store_true")
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code or 2)
    return run_stack(
        cwd=Path.cwd(),
        base_branch=args.base,
        ledger_path=args.ledger,
        plan_path=args.plan,
        dry_run=args.dry_run,
    )
