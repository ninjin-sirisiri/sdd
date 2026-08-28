from pathlib import Path
import subprocess
import sys

from gitutil import git, init_repo
from sddlib.ledger import parse_ledger
from sddlib.stack import run_stack

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
STACK = SCRIPTS / "stack-prs"

PLAN = """# Example Implementation Plan

**Goal:** Build the example.

## Task 1: First thing

First body UNIQUE_TASK_ONE.

## Task 2: Second thing

Second body UNIQUE_TASK_TWO.
"""


def _two_task_repo(tmp_path: Path) -> tuple[Path, Path]:
    init_repo(tmp_path)
    git(tmp_path, "checkout", "-b", "main")
    c0 = git(tmp_path, "rev-parse", "--short", "HEAD").strip()
    (tmp_path / "t1.txt").write_text("1")
    git(tmp_path, "add", "t1.txt")
    git(tmp_path, "-c", "user.email=sdd@test", "-c", "user.name=sdd", "commit", "-m", "t1")
    c1 = git(tmp_path, "rev-parse", "--short", "HEAD").strip()
    (tmp_path / "t2.txt").write_text("2")
    git(tmp_path, "add", "t2.txt")
    git(tmp_path, "-c", "user.email=sdd@test", "-c", "user.name=sdd", "commit", "-m", "t2")
    c2 = git(tmp_path, "rev-parse", "--short", "HEAD").strip()
    ledger = tmp_path / "progress.md"
    ledger.write_text(
        f"Task 1: complete (commits {c0}..{c1}, review clean)\n"
        f"Task 2: complete (commits {c1}..{c2}, review clean)\n"
    )
    plan = tmp_path / "plan.md"
    plan.write_text(PLAN)
    return ledger, plan


def test_parse_ledger_ignores_rulings() -> None:
    text = (
        "Ruling: picked names — clarity — low\n"
        "Task 1: complete (commits abc1234..def5678, review clean)\n"
        "Task 2: complete (commits def5678..aaa9012, review clean)\n"
    )
    items = parse_ledger(text)
    assert [i.number for i in items] == [1, 2]
    assert items[0].base == "abc1234"
    assert items[1].head == "aaa9012"


def test_dry_run_does_not_create_branches_or_call_hooks(tmp_path: Path) -> None:
    ledger, plan = _two_task_repo(tmp_path)
    before_refs = git(tmp_path, "show-ref")
    called: list[str] = []

    def boom(name: str):
        def _inner(*args, **kwargs):
            called.append(name)
            raise AssertionError(f"{name} called")

        return _inner

    code = run_stack(
        cwd=tmp_path,
        base_branch="main",
        ledger_path=ledger,
        plan_path=plan,
        dry_run=True,
        update_ref=boom("update_ref"),
        push=boom("push"),
        gh=boom("gh"),
    )
    assert code == 0
    assert called == []
    assert git(tmp_path, "show-ref") == before_refs
    result = subprocess.run(
        [
            sys.executable,
            str(STACK),
            "--base",
            "main",
            "--ledger",
            str(ledger),
            "--plan",
            str(plan),
            "--dry-run",
        ],
        cwd=tmp_path,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stderr
    assert "sdd-stack/task-1" in result.stdout
    assert "sdd-stack/task-2" in result.stdout


def test_missing_ledger_nonzero(tmp_path: Path) -> None:
    empty = tmp_path / "progress.md"
    empty.write_text("")
    plan = tmp_path / "plan.md"
    plan.write_text(PLAN)
    result = subprocess.run(
        [
            sys.executable,
            str(STACK),
            "--base",
            "main",
            "--ledger",
            str(empty),
            "--plan",
            str(plan),
            "--dry-run",
        ],
        cwd=tmp_path,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 1


def test_real_mode_points_branches(tmp_path: Path) -> None:
    ledger, plan = _two_task_repo(tmp_path)
    refs: list[tuple[str, str]] = []
    pushes: list[str] = []
    gh_calls: list[list[str]] = []

    def update_ref(branch: str, sha: str) -> None:
        refs.append((branch, sha))

    def push(branch: str) -> None:
        pushes.append(branch)

    def gh(args: list[str]) -> str:
        gh_calls.append(args)
        return "https://example.test/pr/" + str(len(gh_calls))

    code = run_stack(
        cwd=tmp_path,
        base_branch="main",
        ledger_path=ledger,
        plan_path=plan,
        dry_run=False,
        update_ref=update_ref,
        push=push,
        gh=gh,
    )
    assert code == 0
    assert [b for b, _ in refs] == ["sdd-stack/task-1", "sdd-stack/task-2"]
    assert pushes == ["sdd-stack/task-1", "sdd-stack/task-2"]
    bases = []
    titles = []
    bodies = []
    for args in gh_calls:
        bases.append(args[args.index("--base") + 1])
        titles.append(args[args.index("--title") + 1])
        bodies.append(args[args.index("--body") + 1])
    assert bases == ["main", "sdd-stack/task-1"]
    assert "First thing" in titles[0]
    assert "Second thing" in titles[1]
    assert "Build the example" in bodies[0]
    assert "Build the example" in bodies[1]
