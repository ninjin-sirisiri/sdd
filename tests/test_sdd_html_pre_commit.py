from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

from gitutil import git, init_repo


ROOT = Path(__file__).resolve().parents[1]
WRAPPER = ROOT / "scripts/sdd-html-pre-commit"
CLI = ROOT / "scripts/html-docs"
FIXTURE = ROOT / "tests/fixtures"


def digest(content: bytes) -> str:
    return f"sha256:{hashlib.sha256(content).hexdigest()}"


def make_repo(repo: Path) -> tuple[Path, Path]:
    init_repo(repo)
    source = repo / "CONTEXT.md"
    companion = repo / "CONTEXT.html"
    source.write_bytes((FIXTURE / "glossary/CONTEXT.md").read_bytes())
    companion.write_bytes((FIXTURE / "glossary/CONTEXT.html").read_bytes())
    css = repo / "docs/sdd/assets/sdd.css"
    css.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(FIXTURE / "docs/sdd/assets/sdd.css", css)
    git(repo, "add", ".")
    git(
        repo,
        "-c",
        "user.email=sdd@test",
        "-c",
        "user.name=sdd",
        "commit",
        "-m",
        "base",
    )
    return source, companion


def update_pair(source: Path, companion: Path) -> None:
    old_source = source.read_bytes()
    new_source = old_source.replace(b"Ordering", b"Vocabulary", 1)
    assert new_source != old_source
    source.write_bytes(new_source)
    html = companion.read_text(encoding="utf-8")
    html = html.replace("Ordering", "Vocabulary")
    html = html.replace('id="ordering"', 'id="vocabulary"')
    companion.write_text(html.replace(digest(old_source), digest(new_source)), encoding="utf-8")


def run_wrapper(
    repo: Path,
    *args: str,
    extra_env: dict[str, str] | None = None,
    cwd: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["SDD_PACK_ROOT"] = str(ROOT)
    environment["GIT_CONFIG_GLOBAL"] = os.devnull
    environment.pop("SDD_PRE_COMMIT_DELEGATE", None)
    if extra_env:
        environment.update(extra_env)
    return subprocess.run(
        [str(WRAPPER), *args],
        cwd=cwd or repo,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )


def write_delegate(path: Path, status: int, marker: Path) -> bytes:
    content = (
        "#!/bin/sh\n"
        'printf \'cwd=%s\\n\' "$PWD" > "$DELEGATE_MARKER"\n'
        'for argument do printf \'arg=%s\\n\' "$argument" >> "$DELEGATE_MARKER"; done\n'
        f"exit {status}\n"
    ).encode()
    path.write_bytes(content)
    path.chmod(0o755)
    return content


def delegate_environment(marker: Path) -> dict[str, str]:
    return {"DELEGATE_MARKER": str(marker)}


def test_staged_pass_runs_from_repository_root_and_allows_commit(tmp_path: Path) -> None:
    source, companion = make_repo(tmp_path)
    update_pair(source, companion)
    git(tmp_path, "add", "CONTEXT.md", "CONTEXT.html")

    nested = tmp_path / "nested"
    nested.mkdir()
    process = run_wrapper(tmp_path, "--from-hook", "value with spaces", cwd=nested)

    assert process.returncode == 0
    assert json.loads(process.stdout)["decision"] == "allow"
    assert process.stderr == ""


def test_staged_failure_stops_before_delegate(tmp_path: Path) -> None:
    source, _companion = make_repo(tmp_path)
    source.write_bytes(source.read_bytes() + b"\nChanged\n")
    git(tmp_path, "add", "CONTEXT.md")
    marker = tmp_path / "delegate-marker"
    delegate = tmp_path / "delegate"
    write_delegate(delegate, 0, marker)

    process = run_wrapper(
        tmp_path,
        extra_env={
            **delegate_environment(marker),
            "SDD_PRE_COMMIT_DELEGATE": str(delegate),
        },
    )

    assert process.returncode == 1
    assert json.loads(process.stdout)["decision"] == "deny"
    assert not marker.exists()


def test_absent_delegate_returns_success_after_freshness_check(tmp_path: Path) -> None:
    make_repo(tmp_path)

    process = run_wrapper(tmp_path, "--no-delegate")

    assert process.returncode == 0
    assert json.loads(process.stdout)["decision"] == "allow"


def test_existing_delegate_passes_arguments_and_status(tmp_path: Path) -> None:
    make_repo(tmp_path)
    hook = tmp_path / ".git/hooks/pre-commit.sdd-existing"
    marker = tmp_path / "existing-marker"
    hook_bytes = write_delegate(hook, 0, marker)

    process = run_wrapper(
        tmp_path,
        "--hook-arg",
        "value with spaces",
        extra_env=delegate_environment(marker),
    )

    assert process.returncode == 0
    assert hook.read_bytes() == hook_bytes
    assert marker.read_text(encoding="utf-8").splitlines() == [
        f"cwd={tmp_path}",
        "arg=--hook-arg",
        "arg=value with spaces",
    ]


def test_existing_delegate_is_found_in_a_linked_worktree_with_core_hooks_path(
    tmp_path: Path,
) -> None:
    make_repo(tmp_path)
    linked = tmp_path / "linked"
    git(tmp_path, "worktree", "add", str(linked), "HEAD")
    hooks_path = tmp_path / ".githooks"
    git(tmp_path, "config", "--local", "core.hooksPath", str(hooks_path))
    hook = hooks_path / "pre-commit.sdd-existing"
    marker = tmp_path / "linked-marker"
    hook.parent.mkdir()
    write_delegate(hook, 0, marker)

    process = run_wrapper(
        tmp_path,
        "--linked",
        extra_env=delegate_environment(marker),
        cwd=linked,
    )

    assert process.returncode == 0
    assert marker.read_text(encoding="utf-8").splitlines() == [
        f"cwd={linked}",
        "arg=--linked",
    ]


def test_existing_delegate_failure_status_is_preserved(tmp_path: Path) -> None:
    make_repo(tmp_path)
    hook = tmp_path / ".git/hooks/pre-commit.sdd-existing"
    marker = tmp_path / "existing-marker"
    write_delegate(hook, 19, marker)

    process = run_wrapper(tmp_path, extra_env=delegate_environment(marker))

    assert process.returncode == 19
    assert marker.exists()


def test_explicit_delegate_takes_precedence_over_existing_hook(tmp_path: Path) -> None:
    make_repo(tmp_path)
    existing_marker = tmp_path / "existing-marker"
    explicit_marker = tmp_path / "explicit-marker"
    existing = tmp_path / ".git/hooks/pre-commit.sdd-existing"
    explicit = tmp_path / "explicit-delegate"
    write_delegate(existing, 17, existing_marker)
    write_delegate(explicit, 23, explicit_marker)

    process = run_wrapper(
        tmp_path,
        extra_env={
            **delegate_environment(explicit_marker),
            "SDD_PRE_COMMIT_DELEGATE": str(explicit),
        },
    )

    assert process.returncode == 23
    assert explicit_marker.exists()
    assert not existing_marker.exists()


def test_ci_base_invocation_checks_the_complete_pr_diff(tmp_path: Path) -> None:
    source, companion = make_repo(tmp_path)
    base_ref = git(tmp_path, "rev-parse", "HEAD").strip()
    update_pair(source, companion)
    git(tmp_path, "add", "CONTEXT.md", "CONTEXT.html")
    git(
        tmp_path,
        "-c",
        "user.email=sdd@test",
        "-c",
        "user.name=sdd",
        "commit",
        "-m",
        "fresh-pair",
    )

    environment = os.environ.copy()
    environment["SDD_PACK_ROOT"] = str(ROOT)
    process = subprocess.run(
        [
            "python3",
            str(CLI),
            "check",
            "--base",
            base_ref,
        ],
        cwd=tmp_path,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )

    assert process.returncode == 0
    assert json.loads(process.stdout)["decision"] == "allow"


def test_missing_pack_root_fails_without_touching_existing_hook(tmp_path: Path) -> None:
    make_repo(tmp_path)
    hook = tmp_path / ".git/hooks/pre-commit.sdd-existing"
    hook_content = b"#!/bin/sh\nexit 0\n"
    hook.write_bytes(hook_content)
    hook.chmod(0o755)
    environment = os.environ.copy()
    environment.pop("SDD_PACK_ROOT", None)
    environment.pop("SDD_PRE_COMMIT_DELEGATE", None)

    process = subprocess.run(
        [str(WRAPPER)],
        cwd=tmp_path,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )

    assert process.returncode == 2
    assert hook.read_bytes() == hook_content
