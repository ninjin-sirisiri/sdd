from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import subprocess

import pytest

from gitutil import git, init_repo


ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts" / "html-docs"
FIXTURES = ROOT / "tests" / "fixtures"


def digest(content: bytes) -> str:
    return f"sha256:{hashlib.sha256(content).hexdigest()}"


def run_cli(
    repo: Path,
    *args: str,
    payload: object | None = None,
) -> subprocess.CompletedProcess[str]:
    input_text = None if payload is None else json.dumps(payload)
    return subprocess.run(
        [str(CLI), *args],
        cwd=repo,
        input=input_text,
        text=True,
        capture_output=True,
    )


def result(process: subprocess.CompletedProcess[str]) -> dict[str, object]:
    assert process.stdout.endswith("\n")
    assert process.stderr == ""
    return json.loads(process.stdout)


def copy_fixture(repo: Path, kind: str, stem: str) -> tuple[Path, Path]:
    if kind == "glossary":
        relative = Path("CONTEXT.md")
    elif kind == "adr":
        relative = Path("docs/adr") / f"{stem}.md"
    elif kind == "spec":
        relative = Path("docs/sdd/specs") / f"{stem}.md"
    else:
        relative = Path("docs/sdd/plans") / f"{stem}.md"
    source = repo / relative
    companion = source.with_suffix(".html")
    source.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(FIXTURES / kind / f"{stem}.md", source)
    shutil.copyfile(FIXTURES / kind / f"{stem}.html", companion)
    css = repo / "docs/sdd/assets/sdd.css"
    css.parent.mkdir(parents=True, exist_ok=True)
    css.write_text("/* test stylesheet */\n", encoding="utf-8")
    return source, companion


def commit_all(repo: Path, message: str = "change") -> None:
    git(repo, "add", ".")
    git(repo, "-c", "user.email=sdd@test", "-c", "user.name=sdd", "commit", "-m", message)


def update_digest(companion: Path, old: bytes, new: bytes) -> None:
    companion.write_text(
        companion.read_text(encoding="utf-8").replace(digest(old), digest(new)),
        encoding="utf-8",
    )


def test_edit_check_returns_policy_json_and_current_digest(tmp_path: Path) -> None:
    source = tmp_path / "CONTEXT.md"
    source.write_bytes(b"# Context\n")

    process = run_cli(
        tmp_path,
        "edit-check",
        payload={"operation": "edit", "paths": ["CONTEXT.md"]},
    )

    assert process.returncode == 0
    assert result(process) == {
        "decision": "allow",
        "message": "Markdown changed; author CONTEXT.html separately.",
        "paths": ["CONTEXT.md", "CONTEXT.html"],
        "expected_digests": {"CONTEXT.html": digest(b"# Context\n")},
    }


@pytest.mark.parametrize(
    ("payload", "needle"),
    (
        ("not json", "JSON object"),
        ({"operation": "edit", "paths": [], "unknown": []}, "unknown"),
        ({"operation": "read", "paths": []}, "operation"),
    ),
)
def test_edit_check_rejects_invalid_input_with_exit_two(
    tmp_path: Path, payload: object, needle: str
) -> None:
    process = run_cli(tmp_path, "edit-check", payload=payload)

    assert process.returncode == 2
    assert needle.casefold() in str(result(process)["message"]).casefold()
    assert result(process)["decision"] == "deny"


def test_edit_check_rejects_malformed_json_with_exit_two(tmp_path: Path) -> None:
    process = subprocess.run(
        [str(CLI), "edit-check"],
        cwd=tmp_path,
        input="{",
        text=True,
        capture_output=True,
    )

    assert process.returncode == 2
    assert "valid JSON" in str(result(process)["message"])


def test_edit_check_does_not_modify_repository_state(tmp_path: Path) -> None:
    source = tmp_path / "CONTEXT.md"
    companion = tmp_path / "CONTEXT.html"
    source.write_bytes(b"# Context\n")
    companion.write_text('<meta name="sdd-source-digest" content="sha256:' + "0" * 64 + '">', encoding="utf-8")
    before = sorted(path.relative_to(tmp_path).as_posix() for path in tmp_path.rglob("*"))

    process = run_cli(
        tmp_path,
        "edit-check",
        payload={"operation": "edit", "paths": ["CONTEXT.html"]},
    )

    assert process.returncode == 0
    assert sorted(path.relative_to(tmp_path).as_posix() for path in tmp_path.rglob("*")) == before
    assert companion.read_text(encoding="utf-8").endswith(">")


def test_check_explicit_paths_validates_a_complete_pair(tmp_path: Path) -> None:
    init_repo(tmp_path)
    source, companion = copy_fixture(tmp_path, "glossary", "CONTEXT")
    commit_all(tmp_path, "base")
    old = source.read_bytes()
    new = old.replace(b"Ordering", b"Vocabulary", 1)
    source.write_bytes(new)
    companion.write_text(
        companion.read_text(encoding="utf-8")
        .replace("Ordering", "Vocabulary")
        .replace('id="ordering"', 'id="vocabulary"'),
        encoding="utf-8",
    )
    update_digest(companion, old, new)

    process = run_cli(tmp_path, "check", "--paths", "CONTEXT.md", "CONTEXT.html")

    assert process.returncode == 0
    checked = result(process)
    assert checked["decision"] == "allow"
    assert checked["paths"] == ["CONTEXT.md", "CONTEXT.html"]
    assert checked["violations"] == []


def test_check_staged_rejects_markdown_only_change(tmp_path: Path) -> None:
    init_repo(tmp_path)
    source, _companion = copy_fixture(tmp_path, "glossary", "CONTEXT")
    commit_all(tmp_path, "base")
    source.write_bytes(source.read_bytes() + b"\nChanged\n")
    git(tmp_path, "add", "CONTEXT.md")

    process = run_cli(tmp_path, "check", "--staged")

    assert process.returncode == 1
    checked = result(process)
    assert checked["decision"] == "deny"
    assert "CONTEXT.html" in str(checked["message"])
    assert checked["expected_digests"] == {
        "CONTEXT.html": digest(source.read_bytes())
    }


def test_check_staged_rejects_html_only_change_even_when_valid(tmp_path: Path) -> None:
    init_repo(tmp_path)
    source, companion = copy_fixture(tmp_path, "glossary", "CONTEXT")
    commit_all(tmp_path, "base")
    companion.write_text(
        companion.read_text(encoding="utf-8").replace("Glossary", "Glossary notes"),
        encoding="utf-8",
    )
    git(tmp_path, "add", "CONTEXT.html")

    process = run_cli(tmp_path, "check", "--staged")

    assert process.returncode == 1
    assert "HTML-only" in str(result(process)["message"])
    assert source.exists()


def test_check_staged_allows_css_only_and_unrelated_changes(tmp_path: Path) -> None:
    init_repo(tmp_path)
    copy_fixture(tmp_path, "glossary", "CONTEXT")
    commit_all(tmp_path, "base")
    (tmp_path / "docs/sdd/assets/sdd.css").write_text("/* changed */\n", encoding="utf-8")
    (tmp_path / "notes.txt").write_text("unrelated\n", encoding="utf-8")
    git(tmp_path, "add", ".")

    process = run_cli(tmp_path, "check", "--staged")

    assert process.returncode == 0
    assert result(process)["decision"] == "allow"


def test_check_staged_rejects_stale_complete_pair(tmp_path: Path) -> None:
    init_repo(tmp_path)
    source, companion = copy_fixture(tmp_path, "glossary", "CONTEXT")
    commit_all(tmp_path, "base")
    source.write_bytes(source.read_bytes() + b"\nChanged\n")
    companion.write_text(companion.read_text(encoding="utf-8").replace("Glossary", "Glossary notes"), encoding="utf-8")
    git(tmp_path, "add", "CONTEXT.md", "CONTEXT.html")

    process = run_cli(tmp_path, "check", "--staged")

    assert process.returncode == 1
    checked = result(process)
    assert checked["decision"] == "deny"
    assert any(item["code"] == "digest-mismatch" for item in checked["violations"])  # type: ignore[index]


def test_check_staged_rejects_partial_multi_document_change(tmp_path: Path) -> None:
    init_repo(tmp_path)
    source, companion = copy_fixture(tmp_path, "glossary", "CONTEXT")
    other, _other_companion = copy_fixture(tmp_path, "adr", "0001-use-postgres")
    commit_all(tmp_path, "base")
    old = source.read_bytes()
    new = old.replace(b"Ordering", b"Vocabulary", 1)
    source.write_bytes(new)
    companion.write_text(
        companion.read_text(encoding="utf-8").replace("Ordering", "Vocabulary"),
        encoding="utf-8",
    )
    update_digest(companion, old, new)
    other.write_bytes(other.read_bytes() + b"\nChanged\n")
    git(tmp_path, "add", "CONTEXT.md", "CONTEXT.html", "docs/adr/0001-use-postgres.md")

    process = run_cli(tmp_path, "check", "--staged")

    assert process.returncode == 1
    assert "0001-use-postgres.html" in str(result(process)["message"])


def test_check_staged_allows_a_pair_rename_and_pair_delete(tmp_path: Path) -> None:
    init_repo(tmp_path)
    source, companion = copy_fixture(tmp_path, "glossary", "CONTEXT")
    old_adr, old_adr_html = copy_fixture(tmp_path, "adr", "0001-use-postgres")
    commit_all(tmp_path, "base")
    new_source = tmp_path / "docs/adr/0002-use-postgres.md"
    new_html = new_source.with_suffix(".html")
    new_source.parent.mkdir(parents=True, exist_ok=True)
    old_adr.rename(new_source)
    old_adr_html.rename(new_html)
    git(tmp_path, "add", "-A")
    source.unlink()
    companion.unlink()
    git(tmp_path, "add", "-A")

    process = run_cli(tmp_path, "check", "--staged")

    assert process.returncode == 0
    assert result(process)["decision"] == "allow"


def test_check_staged_validates_the_destination_of_a_pair_rename(tmp_path: Path) -> None:
    init_repo(tmp_path)
    old_source, old_html = copy_fixture(tmp_path, "adr", "0001-use-postgres")
    commit_all(tmp_path, "base")
    new_source = old_source.with_name("0002-use-postgres.md")
    new_html = new_source.with_suffix(".html")
    old_source.rename(new_source)
    old_html.rename(new_html)
    new_html.write_text(
        new_html.read_text(encoding="utf-8").replace(
            'name="sdd-source-digest"', 'name="wrong-digest"'
        ),
        encoding="utf-8",
    )
    git(tmp_path, "add", "-A")

    process = run_cli(tmp_path, "check", "--staged")

    assert process.returncode == 1
    assert any(item["code"] == "digest-metadata" for item in result(process)["violations"])  # type: ignore[index]


def test_check_staged_rejects_one_sided_target_delete(tmp_path: Path) -> None:
    init_repo(tmp_path)
    source, _companion = copy_fixture(tmp_path, "adr", "0001-use-postgres")
    commit_all(tmp_path, "base")
    source.unlink()
    git(tmp_path, "add", "-A")

    process = run_cli(tmp_path, "check", "--staged")

    assert process.returncode == 1
    assert "both" in str(result(process)["message"])


def test_check_base_reads_the_requested_three_dot_diff(tmp_path: Path) -> None:
    init_repo(tmp_path)
    source, companion = copy_fixture(tmp_path, "glossary", "CONTEXT")
    commit_all(tmp_path, "base")
    base = git(tmp_path, "rev-parse", "HEAD").strip()
    old = source.read_bytes()
    new = old.replace(b"Ordering", b"Vocabulary", 1)
    source.write_bytes(new)
    companion.write_text(
        companion.read_text(encoding="utf-8")
        .replace("Ordering", "Vocabulary")
        .replace('id="ordering"', 'id="vocabulary"'),
        encoding="utf-8",
    )
    update_digest(companion, old, new)
    commit_all(tmp_path, "pair")

    process = run_cli(tmp_path, "check", "--base", base)

    assert process.returncode == 0
    assert result(process)["decision"] == "allow"


def test_check_base_allows_explicit_bootstrap_for_html_only_migration(
    tmp_path: Path,
) -> None:
    init_repo(tmp_path)
    source, companion = copy_fixture(tmp_path, "glossary", "CONTEXT")
    companion.write_text("<html>\n</html>\n", encoding="utf-8")
    commit_all(tmp_path, "legacy companion")
    base = git(tmp_path, "rev-parse", "HEAD").strip()
    companion.write_bytes((FIXTURES / "glossary" / "CONTEXT.html").read_bytes())
    commit_all(tmp_path, "bootstrap authored companion")

    process = run_cli(
        tmp_path,
        "check",
        "--base",
        base,
        "--bootstrap",
        source.relative_to(tmp_path).as_posix(),
    )

    assert process.returncode == 0
    checked = result(process)
    assert checked["decision"] == "allow"
    assert checked["violations"] == []


def test_check_rejects_mixed_source_modes_and_missing_mode(tmp_path: Path) -> None:
    for args in (
        ("--staged", "--paths", "CONTEXT.md"),
        ("--paths", "CONTEXT.md", "--staged"),
        ("--paths", "CONTEXT.md", "--base", "HEAD"),
        (),
    ):
        process = run_cli(tmp_path, "check", *args)
        assert process.returncode == 2
        assert result(process)["decision"] == "deny"


def test_bootstrap_reports_only_requested_missing_or_metadata_less_targets(
    tmp_path: Path,
) -> None:
    source, companion = copy_fixture(tmp_path, "glossary", "CONTEXT")
    companion.unlink()
    before = sorted(path.relative_to(tmp_path).as_posix() for path in tmp_path.rglob("*"))

    process = run_cli(tmp_path, "bootstrap", "CONTEXT.md")

    assert process.returncode == 0
    bootstrapped = result(process)
    assert bootstrapped["decision"] == "allow"
    assert bootstrapped["expected_digests"] == {"CONTEXT.html": digest(source.read_bytes())}
    assert bootstrapped["paths"] == ["CONTEXT.md", "CONTEXT.html"]
    assert not companion.exists()
    assert sorted(path.relative_to(tmp_path).as_posix() for path in tmp_path.rglob("*")) == before


def test_bootstrap_rejects_omitted_and_non_target_paths(tmp_path: Path) -> None:
    for args in ((), ("README.md",)):
        process = run_cli(tmp_path, "bootstrap", *args)
        assert process.returncode == 2
        assert result(process)["decision"] == "deny"


def test_doctor_reports_three_registration_states_without_writing(tmp_path: Path) -> None:
    process = run_cli(tmp_path, "doctor")

    assert process.returncode == 1
    checked = result(process)
    assert checked["decision"] == "deny"
    assert [item["host"] for item in checked["registrations"]] == [  # type: ignore[index]
        "cursor",
        "claude",
        "opencode",
    ]
    assert {item["status"] for item in checked["registrations"]} == {"missing"}  # type: ignore[index]


def test_doctor_accepts_compatible_explicit_registration_files(tmp_path: Path) -> None:
    cursor_adapter = tmp_path / "adapters/cursor/html_docs_hook.py"
    cursor_adapter.parent.mkdir(parents=True)
    cursor_adapter.write_text("#!/usr/bin/env python3\n", encoding="utf-8")
    cursor_adapter.chmod(0o755)
    cursor = tmp_path / ".cursor/hooks.json"
    cursor.parent.mkdir()
    cursor.write_text(
        json.dumps(
            {
                "failClosed": True,
                "hooks": {
                        "preToolUse": [{"command": "adapters/cursor/html_docs_hook.py"}],
                        "afterFileEdit": [{"command": "adapters/cursor/html_docs_hook.py"}],
                        "stop": [{"command": "adapters/cursor/html_docs_hook.py"}],
                },
            }
        ),
        encoding="utf-8",
    )
    claude = tmp_path / ".claude/hooks.json"
    claude.parent.mkdir()
    claude_adapter = tmp_path / "adapters/claude/html_docs_hook.py"
    claude_adapter.parent.mkdir(parents=True)
    claude_adapter.write_text("#!/usr/bin/env python3\n", encoding="utf-8")
    claude_adapter.chmod(0o755)
    claude.write_text(
        json.dumps(
            {
                "command": "adapters/claude/html_docs_hook.py",
                "events": ["PreToolUse", "PostToolUse"],
            }
        ),
        encoding="utf-8",
    )
    opencode = tmp_path / ".opencode/plugins/html_docs_plugin.ts"
    opencode.parent.mkdir(parents=True)
    opencode.write_text(
        "export const htmlDocs = true;\n"
        "const before = 'tool.execute.before';\n"
        "const edited = 'file.edited';\n",
        encoding="utf-8",
    )

    process = run_cli(tmp_path, "doctor")

    assert process.returncode == 0
    checked = result(process)
    assert checked["decision"] == "allow"
    assert {item["status"] for item in checked["registrations"]} == {"enabled"}  # type: ignore[index]
