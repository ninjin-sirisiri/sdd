from pathlib import Path
import subprocess
import sys

import pytest

from gitutil import git, init_repo
from sddlib.ledger import extract_goal, extract_task_heading, parse_ledger
from sddlib.stack import _default_update_ref, _zero_oid, main as stack_main
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


def test_parse_ledger_preserves_file_order() -> None:
    text = (
        "Task 2: complete (commits def5678..aaa9012, review clean)\n"
        "Task 1: complete (commits abc1234..def5678, review clean)\n"
    )
    items = parse_ledger(text)
    assert [i.number for i in items] == [2, 1]


def test_extract_baseline_from_ledger() -> None:
    from sddlib.ledger import extract_baseline

    text = (
        "Branch baseline: abcdef1234567890abcdef1234567890abcdef12\n"
        "Task 1: complete (commits abc1234..def5678, review clean)\n"
    )
    assert extract_baseline(text) == "abcdef1234567890abcdef1234567890abcdef12"
    assert extract_baseline("Task 1: complete (commits abc1234..def5678, review clean)\n") is None


def test_extract_task_heading_skips_fenced_fake() -> None:
    plan = (
        "## Task 1: Real one\n\n"
        "~~~\n"
        "## Task 1: Fake\n"
        "~~~\n\n"
        "## Task 2: Real two\n"
    )
    assert extract_task_heading(plan, 1) == "## Task 1: Real one"
    assert extract_task_heading(plan, 2) == "## Task 2: Real two"


def test_extract_goal_skips_fenced_fake() -> None:
    plan = (
        "# Plan\n\n"
        "```\n"
        "**Goal:** fake\n"
        "```\n\n"
        "**Goal:** real goal.\n\n"
        "## Task 1: One\n"
    )
    assert extract_goal(plan) == "real goal."


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
    items = parse_ledger(ledger.read_text(encoding="utf-8"))
    head1 = git(tmp_path, "rev-parse", "--verify", items[0].head).strip()
    head2 = git(tmp_path, "rev-parse", "--verify", items[1].head).strip()
    assert code == 0
    assert refs == [("sdd-stack/task-1", head1), ("sdd-stack/task-2", head2)]
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


def _boom(name: str, called: list[str]):
    def _inner(*args, **kwargs):
        called.append(name)
        raise AssertionError(f"{name} called")

    return _inner


def test_missing_plan_task_is_preflight_failure(tmp_path: Path) -> None:
    ledger, plan = _two_task_repo(tmp_path)
    lines = ledger.read_text(encoding="utf-8").splitlines(keepends=True)
    ledger.write_text(lines[0])
    called: list[str] = []
    code = run_stack(
        cwd=tmp_path,
        base_branch="main",
        ledger_path=ledger,
        plan_path=plan,
        dry_run=True,
        update_ref=_boom("update_ref", called),
        push=_boom("push", called),
        gh=_boom("gh", called),
    )
    assert code == 1
    assert called == []


def test_duplicate_plan_headings_is_preflight_failure(tmp_path: Path) -> None:
    ledger, plan = _two_task_repo(tmp_path)
    plan.write_text(PLAN + "\n## Task 1: Duplicate heading\n")
    called: list[str] = []
    code = run_stack(
        cwd=tmp_path,
        base_branch="main",
        ledger_path=ledger,
        plan_path=plan,
        dry_run=True,
        update_ref=_boom("update_ref", called),
        push=_boom("push", called),
        gh=_boom("gh", called),
    )
    assert code == 1
    assert called == []


def test_empty_range_is_preflight_failure(tmp_path: Path) -> None:
    ledger, plan = _two_task_repo(tmp_path)
    items = parse_ledger(ledger.read_text(encoding="utf-8"))
    ledger.write_text(
        f"Task 1: complete (commits {items[0].head}..{items[0].head}, review clean)\n"
        f"Task 2: complete (commits {items[1].base}..{items[1].head}, review clean)\n"
    )
    called: list[str] = []
    code = run_stack(
        cwd=tmp_path,
        base_branch="main",
        ledger_path=ledger,
        plan_path=plan,
        dry_run=True,
        update_ref=_boom("update_ref", called),
        push=_boom("push", called),
        gh=_boom("gh", called),
    )
    assert code == 1
    assert called == []


def test_duplicate_ledger_task_is_preflight_failure(tmp_path: Path) -> None:
    ledger, plan = _two_task_repo(tmp_path)
    first = ledger.read_text(encoding="utf-8").splitlines()[0]
    ledger.write_text(first + "\n" + first + "\n")
    called: list[str] = []
    code = run_stack(
        cwd=tmp_path,
        base_branch="main",
        ledger_path=ledger,
        plan_path=plan,
        dry_run=True,
        update_ref=_boom("update_ref", called),
        push=_boom("push", called),
        gh=_boom("gh", called),
    )
    assert code == 1
    assert called == []


def test_bad_sha_is_preflight_failure_even_on_dry_run(tmp_path: Path) -> None:
    ledger, plan = _two_task_repo(tmp_path)
    items = parse_ledger(ledger.read_text(encoding="utf-8"))
    ledger.write_text(
        f"Task 1: complete (commits {items[0].base}..deadbee, review clean)\n"
        f"Task 2: complete (commits {items[1].base}..{items[1].head}, review clean)\n"
    )
    called: list[str] = []
    code = run_stack(
        cwd=tmp_path,
        base_branch="main",
        ledger_path=ledger,
        plan_path=plan,
        dry_run=True,
        update_ref=_boom("update_ref", called),
        push=_boom("push", called),
        gh=_boom("gh", called),
    )
    assert code == 1
    assert called == []


def test_reversed_task_range_is_preflight_failure(tmp_path: Path) -> None:
    ledger, plan = _two_task_repo(tmp_path)
    items = parse_ledger(ledger.read_text(encoding="utf-8"))
    ledger.write_text(
        f"Task 1: complete (commits {items[0].head}..{items[0].base}, review clean)\n"
        f"Task 2: complete (commits {items[1].base}..{items[1].head}, review clean)\n"
    )
    called: list[str] = []
    code = run_stack(
        cwd=tmp_path,
        base_branch="main",
        ledger_path=ledger,
        plan_path=plan,
        dry_run=True,
        update_ref=_boom("update_ref", called),
        push=_boom("push", called),
        gh=_boom("gh", called),
    )
    assert code == 1
    assert called == []


def test_discontinuous_range_is_preflight_failure(tmp_path: Path) -> None:
    ledger, plan = _two_task_repo(tmp_path)
    items = parse_ledger(ledger.read_text(encoding="utf-8"))
    ledger.write_text(
        f"Task 1: complete (commits {items[0].base}..{items[0].head}, review clean)\n"
        f"Task 2: complete (commits {items[0].base}..{items[1].head}, review clean)\n"
    )
    called: list[str] = []
    code = run_stack(
        cwd=tmp_path,
        base_branch="main",
        ledger_path=ledger,
        plan_path=plan,
        dry_run=True,
        update_ref=_boom("update_ref", called),
        push=_boom("push", called),
        gh=_boom("gh", called),
    )
    assert code == 1
    assert called == []


def test_existing_branch_wrong_sha_is_preflight_failure(tmp_path: Path) -> None:
    ledger, plan = _two_task_repo(tmp_path)
    git(tmp_path, "branch", "sdd-stack/task-1", "sdd-base")
    called: list[str] = []
    code = run_stack(
        cwd=tmp_path,
        base_branch="main",
        ledger_path=ledger,
        plan_path=plan,
        dry_run=False,
        update_ref=_boom("update_ref", called),
        push=_boom("push", called),
        gh=_boom("gh", called),
    )
    assert code == 1
    assert called == []
    assert git(tmp_path, "rev-parse", "--abbrev-ref", "sdd-stack/task-1").strip() == "sdd-stack/task-1"


def test_checked_out_wrong_sha_is_preflight_failure(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    ledger, plan = _two_task_repo(repo)
    git(repo, "branch", "sdd-stack/task-1", "sdd-base")
    git(repo, "worktree", "add", str(tmp_path / "linked"), "sdd-stack/task-1")
    called: list[str] = []
    code = run_stack(
        cwd=repo,
        base_branch="main",
        ledger_path=ledger,
        plan_path=plan,
        dry_run=True,
        update_ref=_boom("update_ref", called),
        push=_boom("push", called),
        gh=_boom("gh", called),
    )
    assert code == 1
    assert called == []
    assert "checked out" in capsys.readouterr().err


def test_update_ref_create_only_does_not_move_unexpected_tip(tmp_path: Path) -> None:
    ledger, plan = _two_task_repo(tmp_path)
    items = parse_ledger(ledger.read_text(encoding="utf-8"))
    head1 = git(tmp_path, "rev-parse", "--verify", items[0].head).strip()
    git(tmp_path, "branch", "sdd-stack/task-1", "sdd-base")
    before = git(tmp_path, "rev-parse", "refs/heads/sdd-stack/task-1").strip()
    update = _default_update_ref(tmp_path, {"sdd-stack/task-1": _zero_oid(tmp_path)})
    with pytest.raises(subprocess.CalledProcessError):
        update("sdd-stack/task-1", head1)
    assert git(tmp_path, "rev-parse", "refs/heads/sdd-stack/task-1").strip() == before
    assert before != head1


def test_idempotent_when_refs_already_at_heads(tmp_path: Path) -> None:
    ledger, plan = _two_task_repo(tmp_path)
    items = parse_ledger(ledger.read_text(encoding="utf-8"))
    head1 = git(tmp_path, "rev-parse", "--verify", items[0].head).strip()
    head2 = git(tmp_path, "rev-parse", "--verify", items[1].head).strip()
    git(tmp_path, "update-ref", "refs/heads/sdd-stack/task-1", head1)
    git(tmp_path, "update-ref", "refs/heads/sdd-stack/task-2", head2)
    pushes: list[str] = []
    gh_calls: list[list[str]] = []

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
        push=push,
        gh=gh,
    )
    assert code == 0
    assert git(tmp_path, "rev-parse", "refs/heads/sdd-stack/task-1").strip() == head1
    assert git(tmp_path, "rev-parse", "refs/heads/sdd-stack/task-2").strip() == head2
    assert len(gh_calls) == 2


def test_real_mode_writes_refs_at_full_sha(tmp_path: Path) -> None:
    ledger, plan = _two_task_repo(tmp_path)
    items = parse_ledger(ledger.read_text(encoding="utf-8"))
    head1 = git(tmp_path, "rev-parse", "--verify", items[0].head).strip()
    head2 = git(tmp_path, "rev-parse", "--verify", items[1].head).strip()
    pushes: list[str] = []
    gh_calls: list[list[str]] = []

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
        push=push,
        gh=gh,
    )
    assert code == 0
    assert git(tmp_path, "rev-parse", "refs/heads/sdd-stack/task-1").strip() == head1
    assert git(tmp_path, "rev-parse", "refs/heads/sdd-stack/task-2").strip() == head2
    assert pushes == ["sdd-stack/task-1", "sdd-stack/task-2"]
    assert len(gh_calls) == 2


def test_help_exits_zero() -> None:
    result = subprocess.run(
        [sys.executable, str(STACK), "--help"],
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0
    assert "--dry-run" in result.stdout
    assert stack_main(["--help"]) == 0
