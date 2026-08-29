from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import argparse
import subprocess
import sys

from sddlib.cli import system_exit_code
from sddlib.ledger import TaskComplete, extract_goal, extract_task_heading, parse_ledger
from sddlib.md import plan_task_numbers


def _git(cwd: Path, *args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=cwd, text=True)


def _git_run(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=cwd, text=True, capture_output=True)


def _zero_oid(cwd: Path) -> str:
    result = _git_run(cwd, "rev-parse", "--show-object-format")
    fmt = result.stdout.strip() if result.returncode == 0 else "sha1"
    return "0" * (64 if fmt == "sha256" else 40)


def _resolve_commit(cwd: Path, rev: str) -> str | None:
    result = _git_run(cwd, "rev-parse", "--verify", f"{rev}^{{commit}}")
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def _is_ancestor(cwd: Path, ancestor: str, descendant: str) -> bool:
    result = _git_run(cwd, "merge-base", "--is-ancestor", ancestor, descendant)
    return result.returncode == 0


def _ref_sha(cwd: Path, branch: str) -> str | None:
    result = _git_run(cwd, "rev-parse", "--verify", f"refs/heads/{branch}^{{commit}}")
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def _checked_out_branches(cwd: Path) -> set[str]:
    result = _git_run(cwd, "worktree", "list", "--porcelain")
    if result.returncode != 0:
        return set()
    prefix = "refs/heads/"
    branches: set[str] = set()
    for line in result.stdout.splitlines():
        if line.startswith("branch ") and line[7:].startswith(prefix):
            branches.add(line[7 + len(prefix) :])
    return branches


@dataclass(frozen=True)
class _ReadyTask:
    item: TaskComplete
    base_sha: str
    head_sha: str
    heading: str
    branch: str
    pr_base: str
    expected_old: str


def _preflight(
    *,
    cwd: Path,
    base_branch: str,
    items: list[TaskComplete],
    plan_text: str,
) -> list[_ReadyTask] | str:
    plan_nums = plan_task_numbers(plan_text)
    if not plan_nums:
        return "no tasks in plan"
    if len(plan_nums) != len(set(plan_nums)):
        return f"duplicate task headings in plan: {plan_nums}"
    ledger_nums = [item.number for item in items]
    if len(ledger_nums) != len(set(ledger_nums)):
        return f"duplicate task in ledger: {ledger_nums}"
    if ledger_nums != plan_nums:
        return f"ledger tasks {ledger_nums} do not match plan tasks {plan_nums}"

    zero = _zero_oid(cwd)
    checked_out = _checked_out_branches(cwd)
    ready: list[_ReadyTask] = []
    for index, item in enumerate(items):
        base_sha = _resolve_commit(cwd, item.base)
        if base_sha is None:
            return f"cannot resolve base {item.base} for task {item.number}"
        head_sha = _resolve_commit(cwd, item.head)
        if head_sha is None:
            return f"cannot resolve head {item.head} for task {item.number}"
        if base_sha == head_sha:
            return f"empty commit range for task {item.number}"
        if not _is_ancestor(cwd, base_sha, head_sha):
            return f"base is not an ancestor of head for task {item.number}"
        if ready and ready[-1].head_sha != base_sha:
            return (
                f"discontinuous range between task {ready[-1].item.number} "
                f"and task {item.number}"
            )
        branch = f"sdd-stack/task-{item.number}"
        existing = _ref_sha(cwd, branch)
        if existing is not None and existing != head_sha:
            if branch in checked_out:
                return (
                    f"ref {branch} is checked out and points at {existing} "
                    f"(expected {head_sha})"
                )
            return f"ref {branch} already exists at {existing} (expected {head_sha})"
        expected_old = zero if existing is None else existing
        heading = extract_task_heading(plan_text, item.number) or branch
        pr_base = base_branch if index == 0 else f"sdd-stack/task-{items[index - 1].number}"
        ready.append(
            _ReadyTask(
                item=item,
                base_sha=base_sha,
                head_sha=head_sha,
                heading=heading,
                branch=branch,
                pr_base=pr_base,
                expected_old=expected_old,
            )
        )
    return ready


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
    if not plan_path.is_file():
        print("missing plan", file=sys.stderr)
        return 1
    items = parse_ledger(ledger_path.read_text(encoding="utf-8"))
    if not items:
        print("no complete tasks in ledger", file=sys.stderr)
        return 1
    plan_text = plan_path.read_text(encoding="utf-8")
    prepared = _preflight(
        cwd=cwd,
        base_branch=base_branch,
        items=items,
        plan_text=plan_text,
    )
    if isinstance(prepared, str):
        print(prepared, file=sys.stderr)
        return 1
    goal = extract_goal(plan_text)
    updater = update_ref or _default_update_ref(
        cwd, {task.branch: task.expected_old for task in prepared}
    )
    created: list[str] = []
    for index, task in enumerate(prepared):
        if dry_run:
            print(f"{task.branch} base={task.pr_base}")
            continue
        try:
            updater(task.branch, task.head_sha)
            (push or (_default_push(cwd)))(task.branch)
            url = (gh or (_default_gh(cwd)))(
                [
                    "pr",
                    "create",
                    "--base",
                    task.pr_base,
                    "--head",
                    task.branch,
                    "--title",
                    task.heading,
                    "--body",
                    f"{goal}\n\n{task.heading}",
                ]
            )
            created.append(url.strip())
            print(url.strip())
        except Exception as exc:  # noqa: BLE001
            remaining = [t.item.number for t in prepared[index:]]
            print(f"failed at task {task.item.number}: {exc}", file=sys.stderr)
            print("created: " + ", ".join(created), file=sys.stderr)
            print("remaining: " + ", ".join(str(n) for n in remaining), file=sys.stderr)
            return 1
    return 0


def _default_update_ref(cwd: Path, expected_olds: dict[str, str]):
    def _run(branch: str, sha: str) -> None:
        old = expected_olds[branch]
        _git(cwd, "update-ref", f"refs/heads/{branch}", sha, old)

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
        return system_exit_code(exc)
    return run_stack(
        cwd=Path.cwd(),
        base_branch=args.base,
        ledger_path=args.ledger,
        plan_path=args.plan,
        dry_run=args.dry_run,
    )
